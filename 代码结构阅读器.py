import sys
import os
from PyQt5.QtWidgets import (QApplication, QWidget, QTextEdit, QVBoxLayout, QHBoxLayout, 
                             QListWidget, QSplitter, QPushButton, QFileDialog, QMessageBox, QLabel, QProgressBar)
from PyQt5.QtGui import QDropEvent, QFont
from PyQt5.QtCore import Qt, QThread, pyqtSignal

class FileProcessThread(QThread):
    update_signal = pyqtSignal(str, str, str)
    finished_signal = pyqtSignal()

    def __init__(self, path):
        super().__init__()
        self.path = path
        self.max_files = 1000
        self.max_depth = 5
        self.skip_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.mp3', '.mp4', '.avi', '.mov', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'}

    def run(self):
        file_structure = self.get_file_structure(self.path)
        self.update_signal.emit("structure", file_structure, "structure")
        
        if os.path.isdir(self.path):
            self.process_directory(self.path)
        else:
            self.process_file(self.path)
        
        self.finished_signal.emit()

    def process_directory(self, dir_path, depth=0):
        if depth > self.max_depth:
            return
        
        file_count = 0
        for root, dirs, files in os.walk(dir_path):
            for file in files:
                if file_count >= self.max_files:
                    return
                file_path = os.path.join(root, file)
                self.process_file(file_path)
                file_count += 1

    def get_file_structure(self, start_path):
        output = []
        max_depth = self.max_depth
        
        def print_directory(path, prefix=''):
            nonlocal max_depth
            if max_depth <= 0:
                return
            
            contents = list(os.scandir(path))
            for i, entry in enumerate(contents):
                is_last = (i == len(contents) - 1)
                output.append(f"{prefix}{'└── ' if is_last else '├── '}{entry.name}")
                if entry.is_dir():
                    extension = '    ' if is_last else '│   '
                    max_depth -= 1
                    if max_depth > 0:
                        print_directory(entry.path, prefix + extension)
                    max_depth += 1

        output.append(os.path.basename(start_path))
        print_directory(start_path)
        return '\n'.join(output)

    def process_file(self, file_path):
        file_name = os.path.basename(file_path)
        _, file_extension = os.path.splitext(file_name)
        
        if file_extension.lower() in self.skip_extensions:
            self.update_signal.emit(file_name, "跳过该文件类型", "skipped")
            return

        try:
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                self.update_signal.emit(file_name, content, "file")
        except Exception as e:
            error_msg = f"Error reading {file_path}: {str(e)}"
            self.update_signal.emit(file_name, error_msg, "error")

class FileDropWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.files_content = []
        self.file_structure = ""
        self.process_thread = None

    def initUI(self):
        self.setAcceptDrops(True)
        
        font = QFont()
        font.setPointSize(12)
        font.setBold(True)
        self.setFont(font)

        self.textEdit = QTextEdit()
        self.textEdit.setReadOnly(True)
        self.textEdit.setFont(font)

        self.copyButton = QPushButton("复制")
        self.saveButton = QPushButton("保存")
        self.resetButton = QPushButton("重来")

        self.copyButton.clicked.connect(self.copyContent)
        self.saveButton.clicked.connect(self.saveContent)
        self.resetButton.clicked.connect(self.resetContent)

        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.copyButton)
        buttonLayout.addWidget(self.saveButton)
        buttonLayout.addWidget(self.resetButton)

        leftLayout = QVBoxLayout()
        leftLayout.addLayout(buttonLayout)
        leftLayout.addWidget(self.textEdit)

        self.progressBar = QProgressBar()
        leftLayout.addWidget(self.progressBar)

        leftWidget = QWidget()
        leftWidget.setLayout(leftLayout)

        fileListLabel = QLabel("文件列表：")
        fileListLabel.setFont(font)

        self.fileListWidget = QListWidget()
        self.fileListWidget.setFont(font)

        rightLayout = QVBoxLayout()
        rightLayout.addWidget(fileListLabel)
        rightLayout.addWidget(self.fileListWidget)

        rightWidget = QWidget()
        rightWidget.setLayout(rightLayout)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(leftWidget)
        splitter.addWidget(rightWidget)
        splitter.setSizes([2, 1])

        mainLayout = QHBoxLayout()
        mainLayout.addWidget(splitter)
        self.setLayout(mainLayout)

        self.setGeometry(300, 300, 800, 600)
        self.setWindowTitle('文件拖放提取器')
        self.show()

    def dragEnterEvent(self, event: QDropEvent):
        if event.mimeData().hasUrls():
            event.accept()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            path = url.toLocalFile()
            self.process_thread = FileProcessThread(path)
            self.process_thread.update_signal.connect(self.update_content)
            self.process_thread.finished_signal.connect(self.process_finished)
            self.process_thread.start()
            
            self.copyButton.setEnabled(False)
            self.saveButton.setEnabled(False)
            self.resetButton.setEnabled(False)
            self.progressBar.setRange(0, 0)

    def update_content(self, name, content, content_type):
        if content_type == "structure":
            self.file_structure = content
        elif content_type == "file":
            self.files_content.append((name, content))
            self.fileListWidget.addItem(name)
        elif content_type == "error":
            self.fileListWidget.addItem(f"Error: {name}")
        elif content_type == "skipped":
            self.fileListWidget.addItem(f"Skipped: {name}")
        
        self.update_text_edit()

    def update_text_edit(self):
        full_content = f"文件结构:\n{self.file_structure}\n\n"
        full_content += "文件内容:\n"
        for name, content in self.files_content:
            full_content += f"{'=' * 50}\n"
            full_content += f"文件名: {name}\n"
            full_content += f"{'-' * 50}\n"
            full_content += f"{content}\n\n"
        
        self.textEdit.setText(full_content)

    def process_finished(self):
        self.copyButton.setEnabled(True)
        self.saveButton.setEnabled(True)
        self.resetButton.setEnabled(True)
        self.progressBar.setRange(0, 1)
        self.progressBar.setValue(1)

    def copyContent(self):
        full_content = self.textEdit.toPlainText()
        QApplication.clipboard().setText(full_content)
        QMessageBox.information(self, "复制成功", "内容已复制到剪贴板")

    def saveContent(self):
        file_name, _ = QFileDialog.getSaveFileName(self, "保存文件", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w', encoding='utf-8') as file:
                full_content = self.textEdit.toPlainText()
                file.write(full_content)
            QMessageBox.information(self, "保存成功", f"内容已保存到 {file_name}")

    def resetContent(self):
        self.files_content = []
        self.file_structure = ""
        self.textEdit.clear()
        self.fileListWidget.clear()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = FileDropWidget()
    sys.exit(app.exec_())