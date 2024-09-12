import os
import subprocess
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QMessageBox, QFileDialog, QComboBox)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor

class NewProjectDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create New Project")
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout()
        
        # Project Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Project Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.validate_fields)
        name_layout.addWidget(self.name_edit)
        self.name_status = QLabel()
        name_layout.addWidget(self.name_status)
        layout.addLayout(name_layout)
        
        # Git URL
        git_layout = QVBoxLayout()
        git_input_layout = QHBoxLayout()
        git_input_layout.addWidget(QLabel("Git URL (optional):"))
        self.git_edit = QLineEdit()
        self.git_edit.textChanged.connect(self.validate_fields)
        git_input_layout.addWidget(self.git_edit)
        self.git_status = QLabel("⚪")  # Start with a neutral circle
        git_input_layout.addWidget(self.git_status)
        git_layout.addLayout(git_input_layout)
        self.git_error_label = QLabel()
        self.git_error_label.setStyleSheet("color: red;")
        git_layout.addWidget(self.git_error_label)
        layout.addLayout(git_layout)
        
        # Local Directory
        dir_layout = QHBoxLayout()
        dir_layout.addWidget(QLabel("Local Directory:"))
        self.dir_edit = QLineEdit()
        self.dir_edit.textChanged.connect(self.validate_fields)
        dir_layout.addWidget(self.dir_edit)
        dir_button = QPushButton("Browse")
        dir_button.clicked.connect(self.browse_directory)
        dir_layout.addWidget(dir_button)
        self.dir_status = QLabel()
        dir_layout.addWidget(self.dir_status)
        layout.addLayout(dir_layout)
        
        # Conda Environment
        env_layout = QHBoxLayout()
        env_layout.addWidget(QLabel("Conda Environment:"))
        self.env_combo = QComboBox()
        self.env_combo.currentTextChanged.connect(self.validate_fields)
        env_layout.addWidget(self.env_combo)
        refresh_button = QPushButton("Refresh")
        refresh_button.clicked.connect(self.refresh_conda_environments)
        env_layout.addWidget(refresh_button)
        self.env_status = QLabel()
        env_layout.addWidget(self.env_status)
        layout.addLayout(env_layout)
        
        # Create button
        self.create_button = QPushButton("Create Project")
        self.create_button.setEnabled(False)
        self.create_button.clicked.connect(self.accept)
        layout.addWidget(self.create_button)
        
        self.setLayout(layout)
        
        # Initialize Conda environments
        self.refresh_conda_environments()
    
    def validate_fields(self):
        name_valid = self.name_edit.text().isalnum()
        self.name_status.setText("✓" if name_valid else "✗")
        self.name_status.setStyleSheet(f"color: {'green' if name_valid else 'red'};")
        
        git_url = self.git_edit.text().strip()
        git_valid, git_error = self.is_valid_git_url(git_url) if git_url else (True, "")
        if not git_url:
            self.git_status.setText("⚪")  # Grey circle for no URL
        elif git_valid:
            self.git_status.setText("🟢")  # Green circle for valid URL
        else:
            self.git_status.setText("🟡")  # Yellow circle for invalid URL
        self.git_error_label.setText(git_error)
        
        dir_path = self.dir_edit.text()
        dir_exists = os.path.exists(dir_path) and os.path.isdir(dir_path)
        dir_empty = dir_exists and not os.listdir(dir_path)
        
        if not dir_exists:
            dir_valid = False
            self.dir_status.setText("✗")
            self.dir_status.setStyleSheet("color: red;")
        elif dir_empty:
            dir_valid = True
            self.dir_status.setText("✓")
            self.dir_status.setStyleSheet("color: green;")
        elif git_url and git_valid:
            # Directory not empty, but we have a valid Git URL
            if self.is_git_repo(dir_path) and self.is_repo_up_to_date(dir_path, git_url):
                dir_valid = True
                self.dir_status.setText("✓")
                self.dir_status.setStyleSheet("color: green;")
            else:
                dir_valid = False
                self.dir_status.setText("⚠")
                self.dir_status.setStyleSheet("color: orange;")
        else:
            # Directory not empty, no Git URL
            dir_valid = True
            self.dir_status.setText("⚠")
            self.dir_status.setStyleSheet("color: orange;")
        
        env_valid = self.env_combo.currentText() != ""
        self.env_status.setText("✓" if env_valid else "✗")
        self.env_status.setStyleSheet(f"color: {'green' if env_valid else 'red'};")
        
        self.create_button.setEnabled(name_valid and dir_valid and env_valid and git_valid)
    
    def is_valid_git_url(self, url):
        try:
            result = subprocess.run(["git", "ls-remote", url], capture_output=True, text=True, check=True)
            return True, ""
        except subprocess.CalledProcessError as e:
            if "fatal: repository" in e.stderr and "not found" in e.stderr:
                return False, "Repository not found"
            elif "could not resolve host" in e.stderr.lower():
                return False, "Could not resolve host"
            else:
                return False, f"Git error: {e.stderr.strip()}"
        except FileNotFoundError:
            return False, "Git is not installed or not in PATH"
    
    def is_git_repo(self, path):
        return os.path.isdir(os.path.join(path, '.git'))
    
    def is_repo_up_to_date(self, path, url):
        try:
            current_dir = os.getcwd()
            os.chdir(path)
            subprocess.run(["git", "fetch"], check=True, capture_output=True)
            result = subprocess.run(["git", "status", "-uno"], check=True, capture_output=True, text=True)
            os.chdir(current_dir)
            return "Your branch is up to date" in result.stdout
        except subprocess.CalledProcessError:
            os.chdir(current_dir)
            return False
    
    def browse_directory(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory")
        if directory:
            self.dir_edit.setText(directory)
    
    def refresh_conda_environments(self):
        try:
            result = subprocess.run(["conda", "env", "list", "--json"], capture_output=True, text=True)
            env_data = eval(result.stdout)  # Use eval instead of json.loads for safety
            environments = [os.path.basename(env) for env in env_data["envs"]]
            
            self.env_combo.clear()
            self.env_combo.addItems(environments)
        except subprocess.CalledProcessError:
            QMessageBox.warning(self, "Error", "Failed to retrieve Conda environments. Make sure Conda is installed and accessible.")
    
    def get_project_data(self):
        return {
            "name": self.name_edit.text(),
            "git_url": self.git_edit.text(),
            "local_path": self.dir_edit.text(),
            "conda_env": self.env_combo.currentText()
        }