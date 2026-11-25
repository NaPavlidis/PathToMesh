# Ícones do PathToMesh

| Arquivo | Imagem | Onde é usado |
| --- | --- | --- |
| `PathToMash-icon.ico` / `PathToMash-icon.png` | Ícone do PathToMesh (256x256) | **Ícone principal**: barra de título e barra de tarefas de todas as janelas (app web, app Tk de reserva, launcher, configurações e mensagens), atalhos (Área de Trabalho e Menu Iniciar) e instalador. O `.png` é a imagem de 256 px tirada de dentro do `.ico` (reserva para o `iconphoto`) |
| `1.png` (`1_cabecalho.png`) | Símbolo com "PathToMesh" embaixo | **Logo do cabeçalho**: canto superior esquerdo do app e do launcher, no lugar do nome digitado (o nome fica só no título da janela) |
| `2.png` (`2_cabecalho.png`) | Símbolo + "PathToMesh" na horizontal | **Logo da janela larga**: substitui o 1 no cabeçalho quando a janela passa de 1200 px de largura (ex.: maximizada) |

- As janelas usam o `.ico` (`iconbitmap`); se ele faltar ou não puder ser lido (fora do Windows), usam o `.png` (`iconphoto`).
- `1_cabecalho.png` (93x46) e `2_cabecalho.png` (185x34) são o `1.png` e o `2.png` já reduzidos para a barra de 56 px (média por área, melhor que reduzir na hora). Se você trocar o `1.png` ou o `2.png`, gere de novo esses dois (ou apague-os: aí o app reduz o `.png` grande na hora, com qualidade menor).
- `1.ico` e `2.ico` não são usados pelo código; ficam como reserva.
- `3.ico` e `3.png` (só o símbolo, o ícone principal antigo) não são mais usados pelo código; ficam como reserva.
- Se você trocar o `PathToMash-icon.ico`, gere de novo o `PathToMash-icon.png` (a imagem maior do `.ico`).
- As escolhas ficam em `ICONES`, `LOGOS`, `LARGURA_LOGO_LARGO` e `ALTURA_LOGO`, no `tema_janela.py`.
