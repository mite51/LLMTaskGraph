import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, QFileDialog,
                             QScrollArea, QStyleFactory, QSplitter, QVBoxLayout, QPushButton)
from PyQt5.QtGui import QColor, QFont, QPalette, QIcon, QFontMetrics
from PyQt5.QtCore import Qt

from Widgets import *
from Project import *
from Task import *
from TaskNode import TaskNode_Container
from NewProjectDialog import NewProjectDialog
import Globals

def create_header_widget(text):
    header_widget = QWidget()
    header_layout = QHBoxLayout(header_widget)
    header_layout.setContentsMargins(5, 5, 5, 5)
    
    label = QLabel(text)
    label.setStyleSheet("font-weight: bold; font-size: 14px;")
    
    header_layout.addWidget(label)
    header_layout.addStretch()
    
    header_widget.setStyleSheet("background-color: #e0e0e0; border-bottom: 1px solid #cccccc;")
    return header_widget

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Project Manager")
        self.setGeometry(100, 100, 1200, 800)
        
        # Set the fusion style for a more modern look
        QApplication.setStyle(QStyleFactory.create('Fusion'))
        
        # Set a custom palette
        palette = QPalette()
        palette.setColor(QPalette.Window, QColor(240, 240, 240))
        palette.setColor(QPalette.WindowText, QColor(51, 51, 51))
        palette.setColor(QPalette.Base, QColor(251, 251, 251))
        palette.setColor(QPalette.AlternateBase, QColor(245, 245, 245))
        palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))
        palette.setColor(QPalette.ToolTipText, QColor(51, 51, 51))
        palette.setColor(QPalette.Text, QColor(51, 51, 51))
        palette.setColor(QPalette.Button, QColor(245, 245, 245))
        palette.setColor(QPalette.ButtonText, QColor(51, 51, 51))
        palette.setColor(QPalette.Highlight, QColor(0, 122, 255))
        palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255))
        QApplication.setPalette(palette)

        # Create a QSplitter for the main layout
        main_splitter = QSplitter(Qt.Horizontal)

        # Projects section---
        projects_container = QWidget()
        projects_layout = QVBoxLayout(projects_container)
        projects_layout.setContentsMargins(0, 0, 0, 0)
        projects_layout.setSpacing(0)
        
        projects_header = create_header_widget("Projects")
        projects_header_layout = projects_header.layout()
        
        # Add "+" button for new project
        new_project_button = QPushButton(QIcon("icons/file/new.svg"), "")
        new_project_button.setFixedSize(24, 24)
        new_project_button.setToolTip("New Project")
        new_project_button.clicked.connect(self.create_new_project)

        # Add "Load" button for loading existing projects
        load_project_button = QPushButton(QIcon("icons/file/load.svg"), "")
        load_project_button.setFixedSize(24, 24)
        load_project_button.setToolTip("Load Project")
        load_project_button.clicked.connect(self.load_project)

        projects_header_layout.addWidget(new_project_button)
        projects_header_layout.addWidget(load_project_button)        
        
        projects_layout.addWidget(projects_header)
        
        self.projects_tree = ProjectTreeWidget()
        self.projects_tree.item_selected.connect(self.on_projectview_item_selected)
        
        projects_layout.addWidget(self.projects_tree, 1)
        
        projects_scroll = QScrollArea()
        projects_scroll.setWidget(projects_container)
        projects_scroll.setWidgetResizable(True)
        projects_scroll.setMinimumWidth(200)
        
        # Rest of the code remains unchanged...

        projects_scroll.setMinimumWidth(200)

        # Session section
        session_container = QWidget()
        session_layout = QVBoxLayout(session_container)
        session_layout.setContentsMargins(0, 0, 0, 0)
        session_layout.setSpacing(0)
        
        session_header = create_header_widget("Session")
        session_layout.addWidget(session_header)
        self.session_widget = SessionWidget()
        session_layout.addWidget(self.session_widget, 1)

        # Properties section
        properties_container = QWidget()
        properties_layout = QVBoxLayout(properties_container)
        properties_layout.setContentsMargins(0, 0, 0, 0)
        properties_layout.setSpacing(0)
        
        properties_header = create_header_widget("Properties")
        properties_layout.addWidget(properties_header)
        self.properties_widget = PropertiesWidget()
        properties_layout.addWidget(self.properties_widget, 1)
        properties_container.setMinimumWidth(200)

        # Add widgets to the splitter
        main_splitter.addWidget(projects_scroll)
        main_splitter.addWidget(session_container)
        main_splitter.addWidget(properties_container)

        # Set initial sizes for the splitter
        main_splitter.setSizes([250, 700, 250])

        # Set central widget
        self.setCentralWidget(main_splitter)

        # Set window style
        self.setStyleSheet("""
            QMainWindow {
                background-color: #f0f0f0;
            }
            QWidget {
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton {
                font-weight: bold;
            }                           
            QSplitter::handle {
                background-color: #cccccc;
            }
            QSplitter::handle:hover {
                background-color: #999999;
            }
        """)

        #self.populate_projects()

    def populate_projects(self):
        project1 = Project("Project 1")
        project1.git_URL = "C:/temp/TestGit/.git"
        project1.local_git_path = "C:/temp/TestGitLocal"
        
        taska = Task("Task A")
        taska.project = project1
        project1.add_task(taska)
        
        task1 = Task("Task 1")
        task1.project = project1
        project1.add_task(task1)
        

        task1.LLM_interface.add_session_entry("System", "test\\\\nfile contents", entry_type=ResponseEntryType.FILE, metadata={"filename": "filename", "type": "file"})
        #task1.LLM_interface.add_session_entry("System", diff_file_contents, entry_type=ResponseEntryType.FILE, metadata={"filename": "TEST\\Test.txt", "type": "diff"})
        task1.LLM_interface.add_session_entry("System", "abc123", entry_type=ResponseEntryType.FILE, metadata={"filename": "Images\\image.png", "type": "png"})        

        
        task1.task_graph_root = TaskNode_Container.from_json_file("C:/temp/TestGitLocal/task_graph.json")


        self.projects_tree.add_project(project1)

    def on_projectview_item_selected(self, data, item):
        self.properties_widget.set_object(data)
        if isinstance(data, Task):
            self.session_widget.set_task(data)
        elif isinstance(data, TaskNode_LLM):
            task = item.data(0, Qt.UserRole+1)
            self.session_widget.set_tasknode(task, data)            
        else:
            self.session_widget.set_task(None)
    
    def create_new_project(self):
        dialog = NewProjectDialog(self)
        if dialog.exec_():
            project_data = dialog.get_project_data()
            new_project = Project(project_data["name"])
            new_project.git_URL = project_data["git_url"]
            new_project.local_git_path = project_data["local_path"]
            self.projects_tree.add_project(new_project)

    def load_project(self):
        file_name, _ = QFileDialog.getOpenFileName(self, "Load Project", "", "Project Files (*.project)")
        if file_name:
            try:
                project = Project.load_from_file(file_name)
                self.projects_tree.add_project(project)
            except Exception as e:
                QMessageBox.critical(self, "Load Failed", f"Failed to load project: {str(e)}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    Globals.ProjectManagerWindow = MainWindow()
    Globals.ProjectManagerWindow.show()
    sys.exit(app.exec_())