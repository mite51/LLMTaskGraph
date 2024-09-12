import tempfile
import uuid
import os
import subprocess
import tempfile
import Globals
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QLabel, QFrame, 
                             QPushButton, QMessageBox, QSizePolicy)
from PyQt5.QtCore import Qt
from Util import fix_diff_line_counts

class TextFileWidget(QWidget):
    button_style = """
        QPushButton {
            background-color: #4CAF50;
            border: none;
            color: white;
            padding: 2px 5px;
            text-align: center;
            text-decoration: none;
            font-size: 12px;
            margin: 2px 1px;
            border-radius: 2px;
        }
        QPushButton:hover {
            background-color: #45a049;
        }
        QPushButton:pressed {
            background-color: #3e8e41;
        }
    """

    def __init__(self, sender: str, file_path: str, content_text: str, timestamp: str, embedded_type:str, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.file_contents = content_text
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
        
        message_frame = QFrame()
        message_layout = QVBoxLayout(message_frame)
        message_layout.setContentsMargins(12, 8, 12, 8)
        message_layout.setAlignment(Qt.AlignTop)

        # Info layout (sender and timestamp)
        info_layout = QHBoxLayout()
        info_layout.setAlignment(Qt.AlignTop)
        sender_label = QLabel(sender)
        timestamp_label = QLabel(timestamp)
        info_layout.addWidget(sender_label)
        info_layout.addWidget(timestamp_label, alignment=Qt.AlignRight)

        # File interaction buttons and filename
        file_interaction_layout = QHBoxLayout()
        file_interaction_layout.setAlignment(Qt.AlignLeft)
        
        filename_label = QLabel(os.path.basename(file_path))
        file_interaction_layout.addWidget(filename_label)

        self.open_button = QPushButton("Open")
        self.open_button.setStyleSheet(self.button_style)
        self.open_button.clicked.connect(self.open_file)
        file_interaction_layout.addWidget(self.open_button)
        
        self.open_folder_button = QPushButton("Open Folder")
        self.open_folder_button.setStyleSheet(self.button_style)
        self.open_folder_button.clicked.connect(self.open_folder)
        file_interaction_layout.addWidget(self.open_folder_button)
        if embedded_type == "diff":
            self.apply_diff_button = QPushButton("Apply diff")
            self.apply_diff_button.setStyleSheet(self.button_style)
            self.apply_diff_button.clicked.connect(self.apply_diff)
            file_interaction_layout.addWidget(self.apply_diff_button)
        else:
            file_type_error = QLabel("Unsupported file type")      
            file_interaction_layout.addWidget(file_type_error)

        # Content area
        self.contents = QLabel(content_text)
        self.contents.setStyleSheet("""
            background-color: #E0FFE0;
            border-radius: 0px;
            border-bottom-left-radius: 0px;
        """)        
        self.contents.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.contents.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        message_layout.addLayout(info_layout)
        message_layout.addLayout(file_interaction_layout)
        message_layout.addWidget(self.contents,stretch=0, alignment=Qt.AlignTop)

        # Adjust spacing
        message_layout.setSpacing(4)

        message_frame.setStyleSheet("""
            background-color: #B0FFB0;
            border-radius: 18px;
            border-bottom-left-radius: 5px;
        """)
        sender_label.setStyleSheet("color: #666666; font-size: 10px;")
        timestamp_label.setStyleSheet("color: #666666; font-size: 10px;")
        layout.addWidget(message_frame, alignment=Qt.AlignLeft)

        self.setStyleSheet("background-color: transparent;")
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Minimum)

    def open_file(self):
        filepath = os.path.join(Globals.get_working_directory(), self.file_path)
        if not os.path.exists(filepath):
            QMessageBox.warning(self, 'File Not Found', f'The file {filepath} does not exist.')
        elif os.name == 'nt':  # Windows
            print(f"*** self.file_path={filepath} cwd={Globals.get_working_directory()}")
            os.startfile(filepath, cwd=Globals.get_working_directory())
        elif os.name == 'posix':  # macOS and Linux
            if os.uname().sysname == 'Darwin':  # macOS
                subprocess.call(('open', filepath, ), cwd=Globals.get_working_directory())
            else:  # Linux
                subprocess.call(('xdg-open', filepath), cwd=Globals.get_working_directory())

    def open_folder(self):
        filepath = os.path.join(Globals.get_working_directory(), self.file_path)
        folder_path = os.path.dirname(filepath)
        if not os.path.exists(folder_path):
            QMessageBox.warning(self, 'Folder Not Found', f'The folder {folder_path} does not exist.')        
        elif os.name == 'nt':  # Windows
            os.startfile(folder_path)
        elif os.name == 'posix':  # macOS and Linux
            if os.uname().sysname == 'Darwin':  # macOS
                subprocess.call(('open', folder_path))
            else:  # Linux
                subprocess.call(('xdg-open', folder_path))

    # ensure the text area is a minimum size, or streaming looks kinda bad
    def updateWidth(self):
        if self.parent():
            min_width = max(400, self.parent().width() // 2)
            self.contents.setMinimumWidth(min_width)
            self.contents.setMaximumWidth(max(min_width, self.sizeHint().width()))
            
            self.contents.setMaximumWidth(min_width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateWidth()

        ##https://www.qtcentre.org/threads/62059-QLabel-Word-Wrapping-adds-unnecessary-line-breaks
        #self.contents.setMinimumHeight(self.contents.sizeHint().height())        

    def sizeHint(self):
        return self.layout().sizeHint()
    
    def setText(self, text):
        self.contents.setText(text)
        self.adjustSize()

    def apply_diff(self):
        #LLMs often mess up line counts :/
        self.file_contents = fix_diff_line_counts(self.file_contents)

        # Save the diff to a temp file
        temp_filename = os.path.join(Globals.get_working_directory(), str(uuid.uuid4()))
        with open(temp_filename, 'w', newline='') as f:
            f.write(self.file_contents)

        # Apply the diff
        try:
            result = subprocess.run(['git', 'apply', temp_filename], 
                                    cwd=Globals.get_working_directory(), 
                                    check=True, 
                                    capture_output=True, 
                                    text=True)
            print("Diff applied successfully")
        except subprocess.CalledProcessError as e:
            print(f"Failed to apply diff: {e.stderr}")

        #
        #os.remove(temp_filename)


