# Ícones do PathToMesh

| Arquivo | Imagem | Onde é usado |
| --- | --- | --- |
| `PathToMash-icon.ico` / `PathToMash-icon.png` | Ícone do PathToMesh (quadrado: 16, 20, 24, 32, 40, 48, 64, 96, 128 e 256 px) | **Ícone principal**: barra de título e barra de tarefas de todas as janelas (app web, app Tk de reserva, launcher, configurações e mensagens), atalhos (Área de Trabalho e Menu Iniciar) e instalador. O `.png` é a imagem de 256 px do `.ico` (reserva para o `iconphoto`) |
| `1.png` (`1_cabecalho.png`) | Símbolo com "PathToMesh" embaixo | **Logo do cabeçalho**: canto superior esquerdo do app e do launcher, no lugar do nome digitado (o nome fica só no título da janela) |
| `2.png` (`2_cabecalho.png`) | Símbolo + "PathToMesh" na horizontal | **Logo da janela larga**: substitui o 1 no cabeçalho quando a janela passa de 1200 px de largura (ex.: maximizada) |

- As janelas usam o `.ico` (`iconbitmap`); se ele faltar ou não puder ser lido (fora do Windows), usam o `.png` (`iconphoto`).
- `1_cabecalho.png` (93x46) e `2_cabecalho.png` (185x34) são o `1.png` e o `2.png` já reduzidos para a barra de 56 px (média por área, melhor que reduzir na hora). Se você trocar o `1.png` ou o `2.png`, gere de novo esses dois (ou apague-os: aí o app reduz o `.png` grande na hora, com qualidade menor).
- `1.ico` e `2.ico` não são usados pelo código; ficam como reserva.
- `3.ico` e `3.png` (só o símbolo, o ícone principal antigo) não são mais usados pelo código; ficam como reserva.
- O `PathToMash-icon.ico` foi gerado a partir do `3.png` (a mesma arte, em 1757x784): a arte fica centralizada num quadrado, com a proporção original, as sobras transparentes e uma margem de 1/16 do lado em cada borda. Os tamanhos até 128 px ficam em BMP de 32 bits e o de 256 px em PNG. Como a arte é larga (cerca de 2,24:1), ela ocupa só a faixa do meio do quadrado, e isso é esperado: esticar para preencher o quadrado distorceria o desenho.
- Se você trocar o `PathToMash-icon.ico`, gere de novo o `PathToMash-icon.png` (a imagem de 256 px do `.ico`), sempre quadrados.
- As escolhas ficam em `ICONES`, `LOGOS`, `LARGURA_LOGO_LARGO` e `ALTURA_LOGO`, no `tema_janela.py`.
