import socket  
import hashlib 
import time  

HOST = '127.0.0.1'  
PORTA = 31471 
NOME_CLIENTE = 'Cliente1'

def int_to_big_endian_bytes(n):
    #Converte um inteiro para bytes no formato big-endian (ordem de bytes de maior para menor).(?)
    return n.to_bytes(4, byteorder='big')

def solicitar_transacao(sock):
    sock.send(NOME_CLIENTE.encode('utf-8').ljust(10))  # Envia o nome do cliente, ajustando para 10 bytes
    
    while True:
        sock.send(b'G')  # Envia pedido de transação ('G' = Get Transaction)
        dados = sock.recv(1024)  # Aguarda resposta do servidor

        if not dados:
            print("Servidor não está respondendo. Encerrando cliente.")
            break

        if dados[0:1] == b'W':  # Se não há transações disponíveis
            print("Nenhuma transação disponível. Aguardando...")
            time.sleep(10)
            continue
        
        tipo_mensagem = dados[0:1].decode('utf-8')  # Identifica o tipo de mensagem recebida

        if tipo_mensagem == 'T': 
            id_transacao = int.from_bytes(dados[1:3], byteorder='big')  # ID da transação
            num_clientes = int.from_bytes(dados[3:5], byteorder='big')  # Número de clientes conectados
            tamanho_janela = int.from_bytes(dados[5:9], byteorder='big')  # Janela de validação
            bits_zero = dados[9]  # Quantidade de zeros exigidos no hash
            tam_transacao = int.from_bytes(dados[10:14], byteorder='big')  # Tamanho da transação
            transacao = dados[14:14 + tam_transacao].decode('utf-8')  # Conteúdo da transação

            print(f"Transação recebida: {transacao} (ID: {id_transacao})")
            
            nonce_encontrado = None
            for nonce in range(tamanho_janela):  # Itera sobre a janela de tentativa
                nonce_bytes = int_to_big_endian_bytes(nonce)  # Converte nonce para bytes
                entrada_hash = nonce_bytes + transacao.encode('utf-8')  # Cria entrada para hash
                resultado_hash = hashlib.sha256(entrada_hash).hexdigest()  # Calcula hash SHA-256
                if resultado_hash.startswith('0' * bits_zero):  # Verifica se o hash atende à condição
                    nonce_encontrado = nonce
                    print(f"Nonce encontrado: {nonce} para a transação {id_transacao}")
                    break
            
            if nonce_encontrado is not None:
                while True:
                    resposta = input("Encontrou o nonce? Pressione 'S' para validar: ").strip().upper()
                    if resposta == 'S':
                        sock.send(b'S' + id_transacao.to_bytes(2, byteorder='big') + int_to_big_endian_bytes(nonce_encontrado))
                        print("Nonce enviado ao servidor!")
                        break
                    else:
                        print("Entrada inválida. Pressione 'S' para validar o nonce.")

        # Recebe notificações do servidor
        sock.settimeout(5)  # Define um tempo limite para evitar travamentos
        try:
            notificacao = sock.recv(1024).decode('utf-8')
            if notificacao.startswith("V"):
                print(f">>>>>>> Seu nonce foi validado para a transação {notificacao.split()[1]}. <<<<<<<")
            elif notificacao.startswith("R"):
                print(f">>>>>>> Seu nonce foi rejeitado para a transação {notificacao.split()[1]}. <<<<<<<")
            elif notificacao.startswith("I"):
                print(f"Um outro cliente encontrou um nonce para a transação {notificacao.split()[1]}.")
        except socket.timeout:
            pass

        time.sleep(10)

def main():
    """Função principal do cliente."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Cria socket TCP
    sock.connect((HOST, PORTA))  # Conecta ao servidor
    solicitar_transacao(sock)  # Inicia a comunicação
    sock.close()  # Fecha a conexão

if __name__ == "__main__":
    main()