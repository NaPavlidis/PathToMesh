# Abre o launcher sem a janela preta do console (duplo clique no Windows usa o pythonw).
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import launcher  # noqa: E402

launcher.main()
