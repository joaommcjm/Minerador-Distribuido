import socket
import threading
import sys
import time
import hashlib

host = 'localhost'
porta = 31471

# Variável global para armazenar mensagens do servidor
ultima_mensagem = None
lock = threading.Lock()  # Controle de acesso à variável compartilhada
parar_mineracao = False

# Função para requisitar o nome do cliente
def get_client_name():
    while True:
        nome = input("Digite seu nome (máx. 10 caracteres):\n >>>> ").strip()
        if 1 <= len(nome) <= 10:
            if nome.isalpha():
                return nome.ljust(10)  # Ajusta a variável para ter exatamente 10 caracteres
            else:
                print("Nome inválido! Digite apenas letras.")
        else:
            print("Quantidade de caracteres inválida!")

# Thread que escuta mensagens do servidor e atualiza a ultima mensagem
def listen_server(tcp_sock):
    global ultima_mensagem, parar_mineracao

    while True:
        try:
            dados = tcp_sock.recv(1024)
            if not dados:
                print("Servidor desconectado. Encerrando cliente.")
                sys.exit(1)

            # Garante que apenas uma thread acessa a última mensagem
            with lock:
                type = dados[0:1]

                # Servidor responde protocolo T enviando uma nova transação
                if type == b'T':  
                    ultima_mensagem = dados
                    print("ultima mensagem atualizada")

                # Servidor responde protocolo W (não há transações disponíveis)
                if type == b'W':  
                    print("[INFO] Nenhuma transação disponível. Aguardando...")
                
                # Servidor responde protocolo V, nonce validado.
                if type == b'V':
                    print(f"[INFO] Seu nonce foi validado para a transação {int.from_bytes(dados[1:3], 'big')}.")

                # Servidor informa que outro cliente encontrou o nonce
                if type == b'I':
                    print(f"[INFO] Outro cliente encontrou o nonce para a transação {int.from_bytes(dados[1:3], 'big')}.")
                    parar_mineracao = True

                # Servidor informa que o nonce recebido é inválido
                elif type == b'R':
                    print(f"[INFO] Seu nonce foi rejeitado para a transação {int.from_bytes(dados[1:3], 'big')}.")

                # Servidor informa que está fechando conexão
                elif type == b'Q':
                    print("[INFO] Servidor encerrando. Fechando conexão.")
                    tcp_sock.close()
                    sys.exit(0)


        except Exception as e:
            print(f"[ERRO] Falha ao receber mensagem do servidor: {e}")
            break


# Envia um solicitação de transação ao servidor
def request_transaction(tcp_sock, client_name):
    global ultima_mensagem, parar_mineracao

    while True:

        # Envia um pedido de transação (protocolo G)
        msg = f"G{client_name}".encode("utf-8")
        tcp_sock.sendall(msg)
        print(f"[INFO] Solicitação de transação enviada: {msg.decode()}")

        while ultima_mensagem is None:
            print("Servidor sem transações disponíveis. Tentando novamente...")
            time.sleep(10)
            continue

        with lock:
            dados = ultima_mensagem
            ultima_mensagem = None  # Limpa a variável para evitar reutilização indevida

        parar_mineracao = False
        id_transacao, nonce_encontrado = process_nonce(dados)

        if nonce_encontrado is not None:
            tcp_sock.send(b'S' + id_transacao.to_bytes(2, byteorder='big') + nonce_encontrado.to_bytes(4, byteorder='big'))
            print("Nonce enviado ao servidor!")
        else:
            print("Nonce não encontrado.")

# Processa os dados da transação recebida e realiza a prova de trabalho (mineração).
def process_nonce(dados) -> tuple:

    # Decodifica os bytes de acordo com o protocolo
    id_transacao = int.from_bytes(dados[1:3], byteorder='big')      
    num_cliente = int.from_bytes(dados[3:5], byteorder='big')      
    tamanho_janela = int.from_bytes(dados[5:9], byteorder='big')   
    bits_zero = dados[9]                                            
    tam_transacao = int.from_bytes(dados[10:14], byteorder='big')   
    transacao = dados[14:14 + tam_transacao].decode('utf-8')        

    print(f"\nTransação recebida: {transacao} (ID: {id_transacao})")
    print(f"id_transacao: {id_transacao}")
    print(f"num_cliente: {num_cliente}")
    print(f"tamanho_janela: {tamanho_janela}")
    print(f"bits_zero: {bits_zero}")
    print(f"tam_transacao: {tam_transacao}")
    print(f"transacao: {transacao}")
    
    # Tenta achar o hash válido que corresponda ao nonce + transação
    nonce_encontrado = None
    start = tamanho_janela
    end = start + 1000000

    for nonce in range(start, end):
        if parar_mineracao:
            print("[INFO] Mineração interrompida por notificação do servidor. [I].")
            return id_transacao, None
        
        print(f"Procurando nonce no range ({start}, {end}): {nonce}")                             
        nonce_bytes = nonce.to_bytes(4, byteorder='big')         
        entrada_hash = nonce_bytes + transacao.encode('utf-8')  
        resultado_hash = hashlib.sha256(entrada_hash).digest()   

        # Converte o hash para binário e verifica os bits iniciais
        resultado_hash = bin(int.from_bytes(resultado_hash, 'big'))[2:].zfill(256)

        if resultado_hash.startswith('0' * bits_zero):              
            nonce_encontrado = nonce
            print(f"Nonce encontrado: {nonce} para a transação {id_transacao}")
            break
    
    return id_transacao, nonce_encontrado

def startClient():
    try:
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.connect((host, porta))
    except Exception as e:
        print ("Falha na conexão ao servidor.")
        sys.exit(2)
    return tcp_sock
        

def main():
    client_name = get_client_name()
    tcp_sock = startClient()

    # Cria as threads
    thread_listen = threading.Thread(target=listen_server, args=(tcp_sock,), daemon=True)
    thread_user_request = threading.Thread(target=request_transaction, args=(tcp_sock, client_name), daemon=True)

    print(f"Conectado em: {host, porta}")

    try: 
        thread_listen.start()
        thread_user_request.start()

        thread_listen.join()
        thread_user_request.join()
    except KeyboardInterrupt as e:
        print ("Finalizando por Ctrl-C.") 

if __name__ == "__main__":
    main()