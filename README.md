# Projeto de Mineração Distribuída

Este projeto implementa um sistema de mineração distribuída em Python. O sistema é composto por um servidor (master) e múltiplos clientes (agentes) que realizam a prova de trabalho (PoW) utilizando o algoritmo SHA256. O servidor também opera como um bot do Telegram para fornecer informações sobre o status da mineração.

## Protocolo de Comunicação

O protocolo de comunicação entre o servidor e os clientes é baseado em mensagens codificadas com um formato específico. A seguir estão os detalhes de cada tipo de mensagem e o tamanho das variáveis em bits.

### Mensagens e Tamanho das Variáveis

1. **G nome**:
   - **G**: 1 byte
   - **nome**: 10 caracteres (80 bits)  
     Cada caractere é representado por 1 byte (8 bits), portanto, o nome ocupa 10 bytes ou 80 bits.

2. **T numTransação numCliente tamJanela bitsZero tamTransação transação**:
   - **T**: 1 byte
   - **numTransação**: 2 bytes (16 bits)  
   - **numCliente**: 2 bytes (16 bits)  
   - **tamJanela**: 4 bytes (32 bits)  
   - **bitsZero**: 1 byte (8 bits)  
   - **tamTransação**: 4 bytes (32 bits)  
   - **transação**: É dado por **tamTransação * 8** bits.

3. **W**  1 byte

4. **S numTransação nonce**  
   - **S**: 1 byte
   - **numTransação**: 2 bytes (16 bits)  
   - **nonce**: 4 bytes (32 bits)  

5. **V numTransação**  
   - **V**: 1 byte
   - **numTransação**: 2 bytes (16 bits)  

6. **R numTransação**  
   - **R**: 1 byte
   - **numTransação**: 2 bytes (16 bits)  

7. **I numTransação**  
   - **I**: 1 byte
   - **numTransação**: 2 bytes (16 bits)  

8. **Q** : 1 byte

### Resumo de Bits

| Mensagem | Descrição                                      | Tamanho (bits)                                                                 |
|----------|------------------------------------------------|---------------------------------------------------------------------------------|
| **G**    | Solicitação de transação                      | 80 bits (nome)                                                                  |
| **T**    | Envio de transação                             | 16 bits (numTransação) + 16 bits (numCliente) + 32 bits (tamJanela) + 8 bits (bitsZero) + 32 bits (tamTransação) + tamTransação * 8 bits (transação) |
| **W**    | Não há transações disponíveis                 | 8 bits (sem dados adicionais)                                                    |
| **S**    | Envio de nonce validado                       | 16 bits (numTransação) + 32 bits (nonce)                                         |
| **V**    | Validação do nonce                            | 16 bits (numTransação)                                                           |
| **R**    | Rejeição do nonce                             | 16 bits (numTransação)                                                           |
| **I**    | Notificação de nonce encontrado               | 16 bits (numTransação)                                                           |
| **Q**    | Encerramento da conexão                       | 8 bits (sem dados adicionais)                                                    |

### Pré-requisitos

- Python 3.x
- Bibliotecas Python:
  - `socket`
  - `threading`
  - `hashlib`

## Como Usar
1. **Clone o repositório**:
   ```bash
   git clone https://github.com/joaommcjm/Minerador-Distribuido.git
   cd Minerador-Distribuido

2. **Inicie o servidor**:
   ```bash
   python servidor.py

   
## Comandos do Servidor

O servidor pode receber os seguintes comandos através do bot do Telegram. Cada comando tem uma função específica no gerenciamento das transações e dos clientes.

| Comando           | Descrição                                                                                       | Exemplo de Input                       |
|-------------------|-------------------------------------------------------------------------------------------------|----------------------------------------|
| **/newtrans**     | Solicita a criação de uma nova transação para validação. O usuário deve informar a transação e o número de bits zero necessários para a validação. | `/newtrans`<br>Entrada de transação e bits zero pelo console (não válido para o Telegram) |
| **/validtrans**   | Exibe uma lista das transações validadas até o momento, mostrando o ID da transação, o nonce encontrado e o cliente que validou. | `/validtrans`                          |
| **/pendtrans**    | Exibe uma lista das transações pendentes, com o ID da transação, a transação em si, o número de bits zero necessários e os clientes que estão tentando validar. | `/pendtrans`                           |
| **/clients**      | Exibe uma lista dos clientes conectados ao servidor e as transações que estão validando. | `/clients`                             |
| **/quit**         | Encerra o servidor. Este comando não pode ser usado via Telegram. Só pode ser invocado no console do servidor. | `/quit` (não válido para o Telegram)   |

### Explicação dos Comandos:

- **/newtrans**: Este comando permite ao usuário criar uma nova transação para validação. O usuário será solicitado a inserir a transação e o número de bits zero necessários. Este comando não é válido quando invocado pelo bot do Telegram.
  
- **/validtrans**: Exibe todas as transações que foram validadas até o momento, mostrando o ID, o nonce e o cliente que validou cada transação.

- **/pendtrans**: Exibe todas as transações pendentes de validação, incluindo o ID da transação, os bits zero necessários e os clientes que estão tentando validar cada transação.

- **/clients**: Mostra todos os clientes conectados ao servidor, além das transações que estão tentando validar.

- **/quit**: Encerra o servidor. Este comando não pode ser usado através do Telegram. Ele só é válido quando executado diretamente no console do servidor.

### Observação:
- Se o comando **/newtrans** for invocado pelo Telegram, a resposta será "Comando inválido para o usuário Telegram."
- O comando **/quit** também não pode ser usado via Telegram, já que ele é reservado para o console do servidor.



3. **Inicie e forneça um nome ao cliente**:
   ```bash
   python cliente.py
   
   Digite seu nome (máx. 10 caracteres):
   >>>> João

