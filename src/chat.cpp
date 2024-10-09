#include <iostream>
#include <string>
#include <vector>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <unistd.h>
#include <cstring>

#define PORT 8080
#define BUFFER_SIZE 1024

using namespace std;

// Client information struct
struct ClientInfo {
  string name;
  int socket;
};

// Server class
class Server {
public:
  Server() {
    // Create a socket
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd == -1) {
      perror("Socket creation error");
      exit(1);
    }

    // Set the address information
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = INADDR_ANY;
    address.sin_port = htons(PORT);

    // Bind the socket
    if (bind(sockfd, (struct sockaddr*)&address, sizeof(address)) == -1) {
      perror("Bind error");
      close(sockfd);
      exit(1);
    }

    // Listen for connections
    if (listen(sockfd, 3) == -1) {
      perror("Listen error");
      close(sockfd);
      exit(1);
    }
  }

  // Start the server loop
  void run() {
    while (true) {
      // Accept a new connection
      std::cout << "Wait new client..." << std::endl;
      int new_socket = accept(sockfd, (struct sockaddr*)&client_address, (socklen_t*)&addrlen);
      std::cout << "New connection: " << new_socket << std::endl;
      if (new_socket == -1) {
        perror("Accept error");
        continue;
      }

      // Get the client's name
      char buffer[BUFFER_SIZE];
      recv(new_socket, buffer, BUFFER_SIZE, 0);
      string client_name = buffer;

      // Add the client to the list
      std::unique_lock<std::mutex> lock(client_mutex);
      clients.push_back({client_name, new_socket});
      lock.unlock();

      // Send the updated client list to the new client
      sendClientList(new_socket);

      // Notify all existing clients about the new client
      notifyClients(client_name, new_socket);

      // Start a new thread to handle the client
      thread client_thread(&Server::handleClient, this, new_socket);
      client_thread.detach();
    }
  }

private:
  // Handle client requests
  void handleClient(int client_socket) {
    while (true) {
      char buffer[BUFFER_SIZE];
      int bytes_read = recv(client_socket, buffer, BUFFER_SIZE, 0);
      if (bytes_read == 0) {
        // Client disconnected
        removeClient(client_socket);
        break;
      } else if (bytes_read == -1) {
        perror("Receive error");
        removeClient(client_socket);
        break;
      }

      // Handle the received message
      string message = buffer;
      processMessage(client_socket, message);
    }
  }

  // Send the client list to a specific client
  void sendClientList(int client_socket) {
    std::unique_lock<std::mutex> lock(client_mutex);
    string client_list = "";
    for (const auto& client : clients) {
      client_list += client.name + ":" + to_string(client.socket) + ";";
    }
    std::cout << "Send(sendClientList) to " << client_socket << " " << client_list << std::endl;
    lock.unlock();
    send(client_socket, client_list.c_str(), client_list.length(), 0);
    std::cout << "sendClientList success\n";
  }

  // Notify all clients about a new client
  void notifyClients(string client_name, int client_socket) {
    lock_guard<mutex> lock(client_mutex);
    for (const auto& client : clients) {
      if (client.socket != client_socket) {
        string message = "SERVER: New client connected: " + client_name + " Socket: " + to_string(client_socket);
        std::cout << "Send(notifyClients) to " << client.socket<< " " << message << std::endl;
        send(client.socket, message.c_str(), message.length(), 0);
      }
    }
    std::cout << "notifyClients success\n";
  }

  // Process a received message
  void processMessage(int client_socket, string message) {
    std::cout << "In processMessage" << std::endl;
    // Extract the recipient from the message
    string recipient = message.substr(0, message.find(":"));
    string content = "SERVER: " + message.substr(message.find(":") + 1);

    // Find the recipient's socket
    int recipient_socket = -1;
    lock_guard<mutex> lock(client_mutex);
    for (const auto& client : clients) {
      if (client.name == recipient) {
        recipient_socket = client.socket;
        break;
      }
    }

    // Send the message to the recipient
    if (recipient_socket != -1) {
      send(recipient_socket, content.c_str(), content.length(), 0);
    } else {
      // Handle unknown recipient
      send(client_socket, "SERVER: Recipient not found.\n", strlen("Recipient not found.\n"), 0);
    }
  }

  // Remove a client from the list
  void removeClient(int client_socket) {
    lock_guard<mutex> lock(client_mutex);
    auto it = clients.begin();
    while (it != clients.end()) {
      if (it->socket == client_socket) {
        clients.erase(it);
        break;
      }
      ++it;
    }
    close(client_socket);
  }

  // Socket file descriptor
  int sockfd;

  // Server address information
  struct sockaddr_in address;
  socklen_t addrlen = sizeof(address);

  // Client address information
  struct sockaddr_in client_address;

  // List of clients
  vector<ClientInfo> clients;

  // Mutex for protecting the client list
  mutex client_mutex;
};

// Client class
class Client {
public:
  Client(string name) : name(name) {
    // Create a socket
    sockfd = socket(AF_INET, SOCK_STREAM, 0);
    if (sockfd == -1) {
      perror("Socket creation error");
      exit(1);
    }
  }

  // Connect to the server
  void connectToServer() {
    // Set the server address information
    memset(&address, 0, sizeof(address));
    address.sin_family = AF_INET;
    address.sin_addr.s_addr = inet_addr("127.0.0.1");
    address.sin_port = htons(PORT);

    // Connect to the server
    if (connect(sockfd, (struct sockaddr*)&address, sizeof(address)) == -1) {
      perror("Connection error");
      close(sockfd);
      exit(1);
    }
    std::cout << "Connection to server success" << std::endl;

    // Send the client's name to the server
    send(sockfd, name.c_str(), name.length(), 0);
    std::cout << "Send the client's name to the server success" << std::endl;

    // Receive the client list from the server
    char buffer[BUFFER_SIZE];
    recv(sockfd, buffer, BUFFER_SIZE, 0);
    std::cout << "Receive the client list from the server success" << std::endl;
    string client_list = buffer;
    parseClientList(client_list);
  }

  // Start the client loop
  void run() {
    // Start the input thread
    thread input_thread(&Client::handleInput, this);
    input_thread.detach();

    // Start the receive thread
    thread receive_thread(&Client::handleReceive, this);
    receive_thread.detach();

    // Main loop
    while (true) {
      // Sleep for a short time
      this_thread::sleep_for(chrono::milliseconds(100));
    }
  }

private:
  // Handle input from the user
  void handleInput() {
    while (true) {
      string recipient;
      cout << "Enter recipient name: ";
      cin >> recipient;

      // Find the recipient's socket
      int recipient_socket = -1;
      lock_guard<mutex> lock(client_mutex);
      for (const auto& client : clients) {
        if (client.name == recipient) {
          recipient_socket = client.socket;
          break;
        }
      }
      for(int i = 0;  i < clients.size(); ++i) {
            std::cout << clients[i].name << ":" << clients[i].socket << std::endl;
      }

      if (recipient_socket != -1) {
        string message;
        cout << "Enter message: ";
        cin.ignore(); // Consume the newline character
        getline(cin, message);

        // Send the message to the recipient
        std::cout << "handleInput: send to " << recipient_socket << std::endl;
        send(recipient_socket, (recipient + ":" + message).c_str(), (recipient + ":" + message).length(), 0);
      } else {
        cout << "Recipient not found.\n";
      }
    }
  }

  // Handle messages received from other clients
  void handleReceive() {
    while (true) {
      char buffer[BUFFER_SIZE];
      int bytes_read = recv(sockfd, buffer, BUFFER_SIZE, 0);
      if (bytes_read == 0) {
        // Server disconnected
        cout << "Server disconnected.\n";
        break;
      } else if (bytes_read == -1) {
        perror("Receive error");
        break;
      }

      string message = buffer;
      std::cout << "handleReceive: " << message << std::endl;
      size_t colonPos = message.find(":");
      if (colonPos != string::npos) {
        string sender = message.substr(0, colonPos);
        string content = message.substr(colonPos + 1);

        if (sender == "SERVER") {
          // Process server message
          if (content.find("New client connected:") != string::npos) {
          // Extract new client name and socket
          size_t nameStart = content.find("New client connected: ") + strlen("New client connected: ");
          size_t nameEnd = content.find(" Socket:");
          string newClientName = content.substr(nameStart, nameEnd - nameStart);

          size_t socketStart = content.find("Socket:") + strlen("Socket:");
          string newClientSocketStr = content.substr(socketStart);
          int newClientSocket = stoi(newClientSocketStr);

          // Update the client list
          std::unique_lock<std::mutex> lock(client_mutex);
          clients.push_back({newClientName, newClientSocket});
          lock.unlock();
          
          cout << "New client connected: " << newClientName << " Socket: " << newClientSocket << endl;
        } else {
          // Process message from another client
          cout << sender << ": " << content << endl;
        }
        } else {
          // Invalid message format
          cout << "Invalid message format: " << message << endl;
        }
      }
    }
  }

  // Parse the client list received from the server
  void parseClientList(string client_list) {
    size_t pos = 0;
    string token;
    while ((pos = client_list.find(";")) != string::npos) {
      token = client_list.substr(0, pos);
      if (token.find(":") != string::npos) {
        string client_name = token.substr(0, token.find(":"));
        int client_socket = stoi(token.substr(token.find(":") + 1));
        lock_guard<mutex> lock(client_mutex);
        clients.push_back({client_name, client_socket});
      }
      client_list.erase(0, pos + 1);
    }
  }

  // Client's name
  string name;

  // Socket file descriptor
  int sockfd;

  // Server address information
  struct sockaddr_in address;

  // List of clients
  vector<ClientInfo> clients;

  // Mutex for protecting the client list
  mutex client_mutex;
};

int main() {
  // Choose between server and client
  cout << "Choose mode (server(s)/client(c)): ";
  string mode;
  cin >> mode;

  if (mode == "server" || mode == "s") {
    Server server;
    cout << "Server started.\n";
    server.run();
  } else if (mode == "client" || mode == "c") {
    string client_name;
    cout << "Enter your name: ";
    cin >> client_name;

    Client client(client_name);
    cout << "Client started.\n";
    client.connectToServer();
    client.run();
  } else {
    cout << "Invalid mode.\n";
  }

  return 0;
}