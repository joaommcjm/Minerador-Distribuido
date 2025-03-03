import socket 
import threading 
import hashlib 

HOST = '127.0.0.1' 
PORTA = 31471 

transacoes = {}  
clientes = {}  
transacoes_validas = {} 
lock = threading.Lock() 

def tratar_cliente(conn, addr):
    """Função para tratar a comunicação com um cliente."""
    try:
        print(f"Conexão de {addr} estabelecida.")
        nome = conn.recv(10).decode('utf-8').strip()  # Recebe o nome do cliente e remove espaços em branco
        with lock:
            clientes[nome] = conn  # Adiciona o cliente ao dicionário global
        conn.send(b'G')  # Envia mensagem de boas-vindas ('G' indica solicitação de transação)
        print(f"Cliente {nome} conectado.")    

        while True:
            dados = conn.recv(1024)  # Recebe dados do cliente
            if not dados:
                break  # Se não há dados, encerra a conexão
            
            tipo_mensagem = dados[:1].decode('utf-8')  # Identifica o tipo de mensagem recebida
            if tipo_mensagem == 'G':  # Cliente solicitando uma transação
                enviar_transacao(conn)
            elif tipo_mensagem == 'S':  # Cliente enviando um nonce encontrado
                processar_nonce(dados, nome)
    except Exception as e:
        print(f"Erro com cliente {addr}: {e}")
    finally:
        with lock:
            clientes.pop(nome, None)  # Remove o cliente do dicionário
        conn.close()  # Fecha a conexão
        print(f"Conexão de {addr} encerrada.")

def enviar_transacao(conn):
    """Envia uma transação disponível ao cliente."""
    with lock:
        if transacoes:  # Se há transações disponíveis
            id_transacao, dados_transacao = transacoes.popitem()
        else:
            conn.send(b'W')  # Envia 'W' para indicar que não há transações disponíveis
            return
    
    transacao = dados_transacao['transacao'].encode('utf-8')  
    resposta = bytearray(b'T')  # 'T' indica que é uma transação
    resposta.extend(id_transacao.to_bytes(2, 'big'))  # ID da transação (2 bytes)
    resposta.extend(len(clientes).to_bytes(2, 'big'))  # Número de clientes conectados (2 bytes)
    resposta.extend((1000000).to_bytes(4, 'big'))  # Janela de validação (4 bytes)
    resposta.append(dados_transacao['bits_zero'])  # Número de bits zero necessários
    resposta.extend(len(transacao).to_bytes(4, 'big'))  # Tamanho da transação (4 bytes)
    resposta.extend(transacao)  # Dados da transação
    conn.send(resposta)  # Envia a transação ao cliente

def processar_nonce(dados, nome):
    """Verifica se o nonce enviado pelo cliente é válido."""
    num_transacao = int.from_bytes(dados[1:3], 'big')  # Obtém o ID da transação
    nonce = int.from_bytes(dados[3:7], 'big')  # Obtém o nonce enviado pelo cliente
    
    with lock:
        if num_transacao not in transacoes:
            return  # Ignora se a transação não existir mais
        
        transacao = transacoes[num_transacao]['transacao']  # Obtém os dados da transação
        bits_zero = transacoes[num_transacao]['bits_zero']  # Obtém o critério de bits zero
    
    entrada_hash = nonce.to_bytes(4, 'big') + transacao.encode('utf-8')
    resultado_hash = hashlib.sha256(entrada_hash).hexdigest()  # Calcula o hash
    
    if resultado_hash.startswith('0' * bits_zero):
        with lock:
            transacoes_validas[num_transacao] = {'nonce': nonce, 'cliente': nome}  # Registra a transação validada
        print(f"\nNonce válido encontrado por {nome}: {nonce}")
        
        clientes[nome].send(f"V {num_transacao}".encode('utf-8'))  # Informa ao cliente que o nonce foi validado
        
        with lock:
            for outro_nome, cliente in clientes.items():  # Notifica os outros clientes
                if outro_nome != nome:
                    cliente.send(f"I {num_transacao}".encode('utf-8'))  # 'I' indica que outro cliente validou
            
            for cliente in clientes.values():  # Envia mensagem 'Q' indicando que o servidor vai encerrar
                cliente.send(b'Q')
        
        print("Servidor encerrando conexões com os clientes...")
        exit()  # Finaliza o servidor
    else:
        if nome in clientes:
            clientes[nome].send(f"R {num_transacao}".encode('utf-8'))  # 'R' indica rejeição do nonce

def solicitar_transacao_usuario():
    """Permite que o servidor adicione novas transações manualmente."""
    while True:
        try:
            transacao = input("Informe uma nova transação (T): ")
            if transacao.lower() == 'sair':
                break  # Encerra a entrada manual
            bits_zero = int(input("Bits iniciais zero: "))
            with lock:
                id_transacao = len(transacoes) + 1  # Gera um ID para a nova transação
                transacoes[id_transacao] = {'transacao': transacao, 'bits_zero': bits_zero}
                print(f"Transação {id_transacao} adicionada.")
        except ValueError:
            print("Entrada inválida, tente novamente.")

def main():
    threading.Thread(target=solicitar_transacao_usuario, daemon=True).start()  # Inicia thread para entrada de transações
    servidor = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  # Cria o socket TCP
    servidor.bind((HOST, PORTA))  
    servidor.listen()  
    print(f"\nServidor rodando em {HOST}:{PORTA}")
    
    while True:
        conn, addr = servidor.accept()  # Aguarda conexões de clientes
        threading.Thread(target=tratar_cliente, args=(conn, addr), daemon=True).start()  # Inicia thread para cada cliente

if __name__ == "__main__":
    main()