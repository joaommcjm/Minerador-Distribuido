import socket
import ssl

HOST = "localhost"
PORT = 31471

# Solicitar nome do usuário e garantir que tenha 10 bytes
nome = input("Digite seu nome (máx. 10 caracteres): ")[:10]
NOME_CLIENTE = nome.encode().ljust(10, b' ')

def conectar_ao_servidor():
    try:
        sock = socket.create_connection((HOST, PORT))  # Cria a conexão TCP
        contexto = ssl.create_default_context()  # Cria um contexto SSL
        sock_ssl = contexto.wrap_socket(sock, server_hostname=HOST)  # Aplica SSL na conexão
        return sock_ssl
    except Exception as e:
        print(f"Erro ao conectar ao servidor: {e}")
        return None

def solicitar_transacao(sock):
    if not sock:
        print("Conexão não estabelecida.")
        return
    
    try:
        mensagem = b"G" + NOME_CLIENTE
        sock.sendall(mensagem)  # Envia a mensagem para o servidor
        print("Solicitação de transação enviada...")
        
        resposta = sock.recv(1024)  # Resposta do servidor
        processar_resposta(resposta)
    except Exception as e:
        print(f"Erro ao solicitar transação: {e}")

def processar_resposta(resposta):
    try:
        if resposta.startswith(b"W"):
            print("Nenhuma transação disponível. Espere um pouco e tente novamente.")
        elif resposta.startswith(b"T"):
            num_transacao = int.from_bytes(resposta[1:3], 'big')
            num_clientes = int.from_bytes(resposta[3:5], 'big')
            tam_janela = int.from_bytes(resposta[5:9], 'big')
            bits_zero = int.from_bytes(resposta[9:10], 'big')
            tam_transacao = int.from_bytes(resposta[10:14], 'big')
            transacao = resposta[14:14+tam_transacao].decode(errors='ignore')  # Evita erro de decodificação
            print(f"Recebida transação {num_transacao}: {transacao} ({bits_zero} bits zeros)")
        else:
            print("Resposta desconhecida do servidor.")
    except Exception as e:
        print(f"Erro ao processar resposta: {e}")

# Testando a conexão e solicitação de transação
if __name__ == "__main__":
    try:
        sock = conectar_ao_servidor()
        if sock:
            solicitar_transacao(sock)
            sock.close()
    except Exception as e:
        print(f"Erro na execução do cliente: {e}")