from os.path import dirname, join
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

# Code originally based on example found on 2021-12-10 at
# https://www.pythonguis.com/tutorials/system-tray-mac-menu-bar-applications-pyqt/

app = QApplication([])
app.setQuitOnLastWindowClosed(False)

# Create the icon
icon = QIcon(join(dirname(__file__), 'foliage-icon.png'))

# Create the tray
tray = QSystemTrayIcon()
tray.setIcon(icon)
tray.setVisible(True)

# Create the menu
menu = QMenu()

# Add a Quit option to the menu.
quit = QAction("Quit")
quit.triggered.connect(app.quit)
menu.addAction(quit)

# Add the menu to the tray
tray.setContextMenu(menu)

app.exec_()
