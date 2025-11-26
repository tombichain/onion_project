# gui_master.py
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit
import mariadb
import sys

class MasterGUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Master - Routeurs")
        self.resize(400,300)
        self.layout = QVBoxLayout(self)
        self.refresh_btn = QPushButton("Actualiser")
        self.refresh_btn.clicked.connect(self.refresh)
        self.layout.addWidget(self.refresh_btn)
        self.text = QTextEdit()
        self.layout.addWidget(self.text)

        self.db = mariadb.connect(host="localhost", user="root", password="", database="onion")
        self.cur = self.db.cursor()

    def refresh(self):
        self.cur.execute("SELECT name, ip, port FROM routers")
        rows = self.cur.fetchall()
        out = ""
        for r in rows:
            out += f"{r[0]} - {r[1]}:{r[2]}\n"
        self.text.setPlainText(out)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = MasterGUI()
    w.show()
    sys.exit(app.exec_())
