# Ícones do PathToMesh

| Arquivo | Imagem | Onde é usado |
| --- | --- | --- |
| `3.ico` / `3.png` | Só o símbolo (a curva virando malha), sem texto | **Ícone principal**: barra de título e barra de tarefas de todas as janelas (app, launcher, configurações e mensagens), atalhos (Área de Trabalho e Menu Iniciar) e instalador |
| `1.png` (`1_cabecalho.png`) | Símbolo com "PathToMesh" embaixo | **Logo do cabeçalho**: canto superior esquerdo do app e do launcher, no lugar do nome digitado (o nome fica só no título da janela) |
| `2.png` (`2_cabecalho.png`) | Símbolo + "PathToMesh" na horizontal | **Logo da janela larga**: substitui o 1 no cabeçalho quando a janela passa de 1200 px de largura (ex.: maximizada) |

- As janelas usam o `.ico` (`iconbitmap`); se ele faltar ou não puder ser lido (fora do Windows), usam o `.png` (`iconphoto`).
- `1_cabecalho.png` (93x46) e `2_cabecalho.png` (185x34) são o `1.png` e o `2.png` já reduzidos para a barra de 56 px (média por área, melhor que reduzir na hora). Se você trocar o `1.png` ou o `2.png`, gere de novo esses dois (ou apague-os: aí o app reduz o `.png` grande na hora, com qualidade menor).
- `1.ico` e `2.ico` não são usados pelo código; ficam como reserva.
- As escolhas ficam em `ICONES`, `LOGOS`, `LARGURA_LOGO_LARGO` e `ALTURA_LOGO`, no `tema_janela.py`.
