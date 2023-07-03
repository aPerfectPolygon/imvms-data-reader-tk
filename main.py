import os
import re
import sys
from io import StringIO
from pathlib import Path
from re import findall
from time import sleep

while True:
	try:
		import pandas as pd
		from PyQt5.QtCore import QObject, QThread, pyqtSignal
		from PyQt5.QtWidgets import (
			QApplication,
			QLabel,
			QMainWindow,
			QPushButton,
			QWidget, QLineEdit, QFormLayout, QHBoxLayout, QFileDialog,
		)
		
		break
	except:
		os.system('pip install pandas')
		os.system('pip install pyqt5')

from utils_ import VERSION, convert_24


class Worker(QObject):
	finished = pyqtSignal()
	progress = pyqtSignal(str)
	
	def __init__(self, *args, file_addr=None, **kwargs):
		super().__init__(*args, **kwargs)
		self.file_addr = file_addr
	
	def print_(self, mode: str, data: str):
		print(mode, data)
		self.progress.emit(mode + data)
	
	def run(self):
		sample_rates = []
		n = 1
		for file in convert_24(Path(self.file_addr), print_=self.print_, with_header_data=True):
			self.print_('succ', f'%{int(100 * (n / 24))} converting to human readable timestamps ...')
			n += 1
			
			file = file.rename(file.parent / (file.name + '.tmp'))
			if file.stat().st_size != 0:
				header_data = ''
				with open(file) as f:
					for i in range(4):
						header_data += f.readline()
					data = pd.read_csv(StringIO(f.read()), header=None)
				sample_rates.append(int(findall('Sample Rate: (\d.*)', header_data, re.MULTILINE)[0]))
				data[0] = pd.to_datetime(data[0], unit='s').dt.strftime('%Y-%m-%dT%H:%M:%S.%f')
				data.to_csv(file, header=None, index=False)
			else:
				sample_rates.append(0)
			
			file.rename(file.parent / (file.name.replace('.tmp', '')))
			
		self.print_('succ', '\n'.join(f'Sample Rate {i}: {s}' for i, s in enumerate(sample_rates)))
		self.finished.emit()


class Window(QMainWindow):
	def __init__(self):
		super().__init__()
		
		self.worker_thread = QThread()
		self.worker = Worker()
		
		# setup ui
		self.setWindowTitle(f'WinSDR Translator ({VERSION})')
		self.resize(400, 150)
		self.centralWidget = QWidget()
		self.setCentralWidget(self.centralWidget)
		
		# file picker
		self.btn_choose_file = QPushButton("Choose File")
		self.btn_choose_file.clicked.connect(self.file_picker)
		self.lbl_status = QLabel()
		
		mlayout = QFormLayout()
		mlayout.addWidget(self.btn_choose_file)
		mlayout.addWidget(self.lbl_status)
		
		self.centralWidget.setLayout(mlayout)
	
	def _report(self, data: str):
		if data.startswith('succ'):
			data = data[4:]
			self.lbl_status.setStyleSheet("color: green")
		elif data.startswith('err'):
			data = data[3:]
			self.lbl_status.setStyleSheet("color: red")
		else:
			self.lbl_status.setStyleSheet("color: green")
		
		self.lbl_status.setText(data)
	
	def file_picker(self):
		addr, _ = QFileDialog.getOpenFileName(filter='Data Files(sys*.dat);; All files(*)')
		if addr:
			self.worker_thread = QThread()
			self.worker = Worker(file_addr=addr)
			self.worker.moveToThread(self.worker_thread)
			
			# Connect signals and slots
			self.worker_thread.started.connect(self.worker.run)
			self.worker.finished.connect(self.worker_thread.quit)
			self.worker.finished.connect(self.worker.deleteLater)
			self.worker_thread.finished.connect(self.worker_thread.deleteLater)
			self.worker.progress.connect(self._report)
			
			self.worker_thread.start()
			
			# Final resets
			self.btn_choose_file.setEnabled(False)
			self.worker_thread.finished.connect(lambda: self.btn_choose_file.setEnabled(True))


app = QApplication(sys.argv)
win = Window()
win.show()
sys.exit(app.exec())
