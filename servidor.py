import socket
import ssl
import threading  

HOST = "localhost"  
PORT = 31471

# Lista para armazenar os clientes conectados
clientes = []

def tratar_cliente(conn_ssl, addr):
    #Função que lida com a comunicação com um cliente específico.
    print(f"Cliente conectado: {addr}")
    try:
        while True:
            dados = conn_ssl.recv(1024)
            if not dados:  # Se não receber dados, desconecta o cliente
                break

            if dados.startswith(b"G"): 
                nome_cliente = dados[1:11].decode().strip()  # Obtém o nome do cliente
                print(f"Cliente {nome_cliente} solicitou uma transação")
                enviar_transacao(conn_ssl)  # Envia resposta ao cliente

    except Exception as e:
        print(f"Erro com cliente {addr}: {e}")  # Exibe erros, se ocorrerem
    finally:
        conn_ssl.close()  # Fecha a conexão com o cliente
        print(f"Cliente {addr} desconectado")

def enviar_transacao(conn_ssl):
    conn_ssl.sendall(b"W")  # Envia a mensagem "W" indicando que não há transação
    print("Nenhuma transação disponível, tente novamente.")

def iniciar_servidor():
    # Cria um contexto SSL para comunicação segura
    contexto = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)

    # Carrega o certificado e a chave privada para o SSL/TLS
    #contexto.load_cert_chain(certfile="cert.pem", keyfile="key.pem") (?)
    contexto = ssl._create_unverified_context()  # Usa SSL sem exigir certificados
    
    # Criação do socket TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_socket:
        server_socket.bind((HOST, PORT))
        server_socket.listen()  # Habilita o servidor para aceitar conexões
        print(f"Servidor ouvindo em {HOST}:{PORT}...")

        while True:
            # Aguarda a conexão de um cliente
            sock_cliente, addr = server_socket.accept()
            conn_ssl = contexto.wrap_socket(sock_cliente, server_side=True)
            # Adiciona o cliente à lista de clientes conectados
            clientes.append(conn_ssl)
            threading.Thread(target=tratar_cliente, args=(conn_ssl, addr)).start()

if __name__ == "__main__":
    iniciar_servidor()