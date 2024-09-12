from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QTreeWidget, QTreeWidgetItem, 
                             QLabel, QTextEdit, QLineEdit, QPushButton, QFileDialog,
                             QFrame, QSizePolicy, QMessageBox, QHeaderView, QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QSize, QObject, pyqtSlot
from PyQt5.QtGui import QFont, QIcon, QColor


import Project
from Task import Task, TaskPhase
from TaskNode import TaskNode
import Globals
from TaskNode_LLM import TaskNode_LLM, ResponseEntryType
from Serializable import ISerializable
from TextFileWidget import TextFileWidget

ENABLE_NEW_TASK_TEXT_FIELD = True
DEBUG_ALL_PROMPTS = True
PROJECT_BUTTON_COLUMN_WIDTH = 50
TREEVIEW_ICON_SIZE = 24 

class ProjectTreeWidget(QTreeWidget):
    item_selected = pyqtSignal(object, object)
    _updating = 0
    _refresh_taskgraph_requested = pyqtSignal(object)  # Signal for task refresh requests

    def __init__(self):
        super().__init__()
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setFont(QFont("Segoe UI", 10))

        # Set column count and hide the header
        self.setColumnCount(2)
        self.setHeaderHidden(True)
        self.setIndentation(20)

        # Set the first column to stretch
        header = self.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.Fixed)
        header.setStretchLastSection(False)
        self.setColumnWidth(1, PROJECT_BUTTON_COLUMN_WIDTH)

        self.setIconSize(QSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE))
        
        # deprecating this setup, the icons need to be data driven
        self.phase_icons = {
            "todo": QIcon("icons/todo.svg"),
            "executing": QIcon("icons/executing.svg"),
            "verifying": QIcon("icons/verifying.svg"),
            "complete": QIcon("icons/complete.svg")
        }

        self.delete_icon = QIcon("icons/delete.svg")
        self.reset_icon = QIcon("icons/control/rewind.svg")
        self.itemChanged.connect(self.on_item_changed)
        self.itemClicked.connect(self.on_item_clicked)
        self.setEditTriggers(QTreeWidget.SelectedClicked | QTreeWidget.EditKeyPressed)
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #f0f0f0;
                border: none;
            }
            QTreeWidget::item {
                height: 30px;
                color: #333;
            }
            QTreeWidget::item:selected {
                background-color: #e6f3ff;
            }
            QTreeWidget::item:hover {
                background-color: #f5f5f5;
            }
        """)

        # Connect the new signal to the refresh slot
        self._refresh_taskgraph_requested.connect(self._refresh_taskgraph)
        
    def add_project_buttons(self, project_item):
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)
        
        save_button = QPushButton(QIcon("icons/file/save.svg"), "")
        save_button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
        save_button.setToolTip("Save Project")
        save_button.clicked.connect(lambda: self.on_save_project(project_item))
        
        close_button = QPushButton(QIcon("icons/file/close.svg"), "")
        close_button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
        close_button.setToolTip("Close Project")
        close_button.clicked.connect(lambda: self.on_close_project(project_item))
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        
        self.setItemWidget(project_item, 1, button_widget)

    def add_project(self, project: Project):
        # Check if the project is already in the tree
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item.data(0, Qt.UserRole) == project:
                return  # Project already exists, no need to add it again
           
        project_item = QTreeWidgetItem(self, [project.name])
        project_item.setIcon(0, QIcon("icons/file/project.svg"))
        project_item.setData(0, Qt.UserRole, project)
        self.addTopLevelItem(project_item)
        self.add_project_buttons(project_item)
        
        for task in project.tasks:
            self.add_task_item(project_item, task)
        if ENABLE_NEW_TASK_TEXT_FIELD:            
            self.add_new_task_field(project_item)
        self.expandAll()
        
        # Add the project to the global list
        Globals.add_project(project)
    """
    def add_project_old(self, project: Project):        
        project_item.setIcon(0, QIcon("icons/file/project.svg"))
        project_item.setData(0, Qt.UserRole, project)
        for task in project.tasks:
            self.add_task_item(project_item, task)
        if ENABLE_NEW_TASK_TEXT_FIELD:            
            self.add_new_task_field(project_item)
        self.expandAll()
    """    
    def on_save_project(self, project_item):
        project = project_item.data(0, Qt.UserRole)
        if not project.file_name:
            file_name, _ = QFileDialog.getSaveFileName(self, "Save Project", "", "Project Files (*.project)")
            if file_name:
                project.file_name = file_name
            else:
                return  # User cancelled the save dialog
        
        if project.file_name:
            try:
                project.save_to_file(project.file_name)
                QMessageBox.information(self, "Save Successful", f"Project saved to {project.file_name}")
            except Exception as e:
                QMessageBox.critical(self, "Save Failed", f"Failed to save project: {str(e)}")
        
    def on_close_project(self, project_item):
        reply = QMessageBox.question(self, 'Close Project', 
                                     f"Are you sure you want to close the project '{project_item.text(0)}'?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            project = project_item.data(0, Qt.UserRole)
            self.takeTopLevelItem(self.indexOfTopLevelItem(project_item))
            Globals.remove_project(project)
    
    def add_task_item(self, project_item, task):
        task_item = QTreeWidgetItem(project_item, [task.get_display_name()])
        task_item.setIcon(0, QIcon("icons/file/task.svg"))
        task_item.setFlags(task_item.flags() | Qt.ItemIsEditable)
        task_item.setData(0, Qt.UserRole, task)
        self._updating += 1
        self.update_task_item(task_item)
        self._updating -= 1
        # Ensure the new item is visible
        self.scrollToItem(task_item)

        # Add task graphs to the task item
        if task.task_graph_root:
            self.add_task_node_item(task, task_item, task.task_graph_root)        

        return task_item

    def add_task_node_item(self, task, parent_item: Task, task_node: TaskNode):
        graph_item = QTreeWidgetItem(parent_item, [task_node.name])
        #graph_item.setIcon(0, self.task_graph_icon)
        graph_item.setFlags(graph_item.flags() & ~Qt.ItemIsEditable)
        graph_item.setData(0, Qt.UserRole, task_node)
        graph_item.setData(0, Qt.UserRole+1, task)
        self.add_tasknode_buttons(graph_item)
        
        # Recursively add children
        if task_node.children:
            for child in task_node.children:
                self.add_task_node_item(task, graph_item, child)

    def add_tasknode_buttons(self, tasknode_item):
        tasknode = tasknode_item.data(0, Qt.UserRole)

        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)
        
        rewind_button = QPushButton(QIcon("icons/control/rewind.svg"), "")
        rewind_button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
        rewind_button.setToolTip("Rewind Task")
        #rewind_button.clicked.connect(lambda: self.on_rewind_task_button(tasknode_item))
        
        step_button = QPushButton(QIcon("icons/control/step.svg"), "")
        step_button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
        step_button.setToolTip("Step Task")
        step_button.clicked.connect(lambda: self.on_step_tasknode_button(tasknode_item))

        play_button = QPushButton(QIcon("icons/control/play.svg"), "")
        play_button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
        play_button.setToolTip("Play Task")
        #play_button.clicked.connect(lambda: self.on_play_task_button(tasknode_item))        
        
        tasknode.set_buttons(rewind_button, step_button, play_button)

        button_layout.addWidget(rewind_button)
        button_layout.addWidget(step_button)
        button_layout.addWidget(play_button)
        button_layout.addStretch()
        
        self.setItemWidget(tasknode_item, 1, button_widget)

    def on_step_tasknode_button(self, tasknode_item):
        tasknode = tasknode_item.data(0, Qt.UserRole)
        task = tasknode_item.data(0, Qt.UserRole+1)
        if task.task_context.get_current_node() == tasknode:
            task.step_tasknode()
        else:
            print(f"TaskNode {tasknode.name} is not the current node")

    def add_project_buttons(self, project_item):
        button_widget = QWidget()
        button_layout = QHBoxLayout(button_widget)
        button_layout.setContentsMargins(0, 0, 0, 0)
        button_layout.setSpacing(2)
        
        save_button = QPushButton(QIcon("icons/file/save.svg"), "")
        save_button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
        save_button.setToolTip("Save Project")
        save_button.clicked.connect(lambda: self.on_save_project(project_item))
        
        close_button = QPushButton(QIcon("icons/file/close.svg"), "")
        close_button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
        close_button.setToolTip("Close Project")
        close_button.clicked.connect(lambda: self.on_close_project(project_item))
        
        button_layout.addWidget(save_button)
        button_layout.addWidget(close_button)
        button_layout.addStretch()
        
        self.setItemWidget(project_item, 1, button_widget)


    def add_new_task_field(self, project_item):
        self._updating += 1
        new_task_item = QTreeWidgetItem(project_item, [""])
        new_task_item.setFlags(new_task_item.flags() | Qt.ItemIsEditable)
        new_task_item.setForeground(0, QColor(75, 75, 75))  # Grey color
        new_task_item.setText(0, "new task name.")
        new_task_item.setData(0, Qt.UserRole, {"type": "new_task_placeholder"})
        self._updating -= 1
        return new_task_item

    def update_task_item(self, task_item):
        task = task_item.data(0, Qt.UserRole)
        if isinstance(task, Task):
            task_item.setIcon(0, self.phase_icons["todo"]) #need a way to associate icons in a data driven manner
            if task.task_phase is not TaskPhase.TEST:
                icon = self.delete_icon if task.task_phase == 0 else self.reset_icon
                button = QPushButton(icon, "")
                button.setFixedSize(TREEVIEW_ICON_SIZE, TREEVIEW_ICON_SIZE)
                button.setToolTip("Delete Task" if task.task_phase == 0 else "Reset Task")
                button.clicked.connect(lambda: self.on_task_action(task_item))
                self.setItemWidget(task_item, 1, button)
            else:
                self.removeItemWidget(task_item, 1)
    def on_item_changed(self, item, column):
        if self._updating == 0:
            self._updating += 1
            if ENABLE_NEW_TASK_TEXT_FIELD and isinstance(item.data(0, Qt.UserRole), dict) and item.data(0, Qt.UserRole).get("type") == "new_task_placeholder":
                new_task_name = item.text(0).strip()
                if new_task_name and new_task_name != "New task name.":
                    project_item = item.parent()
                    project = project_item.data(0, Qt.UserRole)
                    new_task = Task(new_task_name, project)
                    project.add_task(new_task)
                    new_task_item = self.add_task_item(project_item, new_task)
                    project_item.removeChild(item)
                    self.add_new_task_field(project_item)
                    self.setCurrentItem(new_task_item)
                elif not new_task_name:
                    item.setText(0, "New task name.")
                    item.setForeground(0, QColor(70, 70, 70))  # Darker grey color
            elif isinstance(item.data(0, Qt.UserRole), Task):
                task = item.data(0, Qt.UserRole)
                task.name = item.text(0)
            self._updating -= 1

    def on_item_clicked(self, item: QTreeWidgetItem, column: int):
        if self._updating == 0:
            self._updating += 1
            if isinstance(item.data(0, Qt.UserRole), dict) and item.data(0, Qt.UserRole).get("type") == "new_task_placeholder":
                self.editItem(item, 0)
            else:
                data = item.data(0, Qt.UserRole)
                self.item_selected.emit(data, item)
            self._updating -= 1

    def on_task_action(self, task_item):
        task = task_item.data(0, Qt.UserRole)
        if task.task_phase == 0:#only allow delete if the task has not started?
            reply = QMessageBox.question(self, 'Delete Task', 
                                         f"Are you sure you want to delete the task '{task.name}'?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                project_item = task_item.parent()
                project = project_item.data(0, Qt.UserRole)
                project.tasks.remove(task)
                project_item.removeChild(task_item)
        elif task.task_phase == TaskPhase.Complete:
            reply = QMessageBox.question(self, 'Reset Task', 
                                         f"Are you sure you want to reset the task '{task.name}' and all subsequent tasks?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                # Perform git reset using task.commit_id
                # This is a placeholder for the actual git reset logic
                print(f"Resetting to commit {task.commit_id}")
                
                project_item = task_item.parent()
                project = project_item.data(0, Qt.UserRole)
                reset_started = False
                for task in project.tasks:
                    if reset_started or task == task_item.data(0, Qt.UserRole):
                        task.task_phase = 0
                        reset_started = True
                
                for i in range(project_item.childCount()):
                    child = project_item.child(i)
                    if child.data(0, Qt.UserRole) != "new_task_placeholder":
                        self.update_task_item(child)

    def _find_task_item(self, task: Task) -> QTreeWidgetItem:
        for i in range(self.topLevelItemCount()):
            project_item = self.topLevelItem(i)
            for j in range(project_item.childCount()):
                task_item = project_item.child(j)
                if task_item.data(0, Qt.UserRole) == task:
                    return task_item
        return None

    def request_refresh_taskgraph(self, task: Task):
        # This method can be called from any thread
        self._refresh_taskgraph_requested.emit(task)
        
    @pyqtSlot(object)
    def _refresh_taskgraph(self, task: Task):
        # Find the task item
        task_item = self._find_task_item(task)
        if not task_item:
            print(f"Task {task.name} not found in the tree.")
            return

        # Remove existing task graph items
        while task_item.childCount() > 0:
            task_item.removeChild(task_item.child(0))

        # Rebuild task graph
        if task.task_graph_root:
            self.add_task_node_item(task, task_item, task.task_graph_root)
            task_item.setExpanded(True)  # Expand the root task node

        self.update_task_item(task_item)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Ensure the second column is always at the edge
        self.setColumnWidth(1, PROJECT_BUTTON_COLUMN_WIDTH)
        self.setColumnWidth(0, self.viewport().width() - PROJECT_BUTTON_COLUMN_WIDTH)

class ChatMessageWidget(QWidget):
    def __init__(self, sender: str, contents: str, timestamp: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 2, 10, 2)
       
        message_frame = QFrame()
        message_layout = QVBoxLayout(message_frame)
        message_layout.setContentsMargins(12, 8, 12, 8)
        message_layout.setAlignment(Qt.AlignTop)

        info_layout = QHBoxLayout()
        info_layout.setAlignment(Qt.AlignTop)
        sender_label = QLabel(sender)
        timestamp_label = QLabel(timestamp)
        info_layout.addWidget(sender_label)
        info_layout.addWidget(timestamp_label, alignment=Qt.AlignRight)        
        
        self.contents = QLabel(contents)
        self.contents.setWordWrap(True)
        self.contents.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self.contents.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        
        message_layout.addLayout(info_layout)
        message_layout.addWidget(self.contents)#,stretch=1,alignment=Qt.AlignTop)
        

        # Adjust spacing
        message_layout.setSpacing(4)        
        
        if sender.lower() != "user":
            message_frame.setStyleSheet("""
                background-color: #E5E5EA;
                border-radius: 18px;
                border-bottom-left-radius: 5px;
            """)
            sender_label.setStyleSheet("color: #666666; font-size: 10px;")
            timestamp_label.setStyleSheet("color: #666666; font-size: 10px;")            
            layout.addWidget(message_frame, alignment=Qt.AlignLeft)
        else:  # User message
            message_frame.setStyleSheet("""
                background-color: #007AFF;
                color: white;
                border-radius: 18px;
                border-bottom-right-radius: 5px;
            """)
            sender_label.setStyleSheet("color: #FFFFFF; font-size: 10px;")
            timestamp_label.setStyleSheet("color: #FFFFFF; font-size: 10px;")            
            layout.addWidget(message_frame, alignment=Qt.AlignRight)

        self.setStyleSheet("background-color: transparent;")
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

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

        #https://www.qtcentre.org/threads/62059-QLabel-Word-Wrapping-adds-unnecessary-line-breaks
        self.contents.setMinimumHeight(self.contents.sizeHint().height())
        self.contents.setMaximumHeight(self.contents.sizeHint().height())

    def sizeHint(self):
        return self.layout().sizeHint()
    
    def setText(self, text):
        self.contents.setText(text)
        self.adjustSize()


class SessionEntryWidget(QWidget):
    session_entry_widget = None
    session_entry = None
    def __init__(self, entry, parent=None):
        super().__init__(parent)
        self.session_entry = entry
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        timestamp = entry.time_stamp.strftime("%Y-%m-%d %H:%M:%S")
        if entry.entry_type == ResponseEntryType.CHAT or entry.entry_type == ResponseEntryType.INSTRUCTION:
            self.session_entry_widget = ChatMessageWidget(entry.sender, entry.content, timestamp)
            layout.addWidget(self.session_entry_widget)
        elif entry.entry_type == ResponseEntryType.FILE:
            embedded_type = entry.metadata["type"]
            self.session_entry_widget = TextFileWidget(entry.sender, entry.metadata["filename"], entry.content, timestamp, embedded_type)
            layout.addWidget(self.session_entry_widget)

    def RefreshContent(self):
        if self.session_entry_widget:
            self.session_entry_widget.setText(self.session_entry.content)
            self.adjustSize()
    
    def sizeHint(self):
        return self.layout().sizeHint()

class SessionViewModel(QObject):
    streaming_update = pyqtSignal()

    def __init__(self, task_node_llm: TaskNode_LLM):
        super().__init__()
        self.task_node_llm = task_node_llm
        self.task_node_llm.connect_streaming_update(self.on_streaming_update)

    def on_streaming_update(self):
        self.streaming_update.emit()

    def get_entries(self):
        return self.task_node_llm.session

    def send_message(self, message):
        self.task_node_llm.add_session_entry("User", message)
        self.task_node_llm.request_llm_response()

    def set_task_node_llm(self, task_node_llm: TaskNode_LLM):
        if self.task_node_llm:
            self.task_node_llm.disconnect_streaming_update(self.on_streaming_update)
        self.task_node_llm = task_node_llm
        self.task_node_llm.connect_streaming_update(self.on_streaming_update)

class SessionWidget(QWidget):

    def __init__(self):
        super().__init__()
        self._task = None

        self.layout = QVBoxLayout(self)
        self.layout.setSpacing(10)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_content = QWidget()
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_layout.setAlignment(Qt.AlignTop)
        self.scroll_layout.setSpacing(10)
        self.scroll_layout.setContentsMargins(10, 10, 10, 10)
        self.scroll_area.setWidget(self.scroll_content)

        self.input_area = QTextEdit()
        self.input_area.setMaximumHeight(100)
        self.input_area.setPlaceholderText("Type your message here...")

        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)

        input_layout = QHBoxLayout()
        input_layout.addWidget(self.input_area)
        input_layout.addWidget(self.send_button)

        self.layout.addWidget(self.scroll_area)
        self.layout.addLayout(input_layout)

        self.view_model = None

    def set_task(self, task: Task):
        self._task = task
        if task is None or task.LLM_interface is None:
            self.set_view_model(None)
        else:
            new_view_model = SessionViewModel(task.LLM_interface)
            self.set_view_model(new_view_model)    
            
    def set_tasknode(self, task: Task, tasknode: TaskNode_LLM):
        self._task = task
        if task is None or tasknode is None:
            self.set_view_model(None)
        else:
            new_view_model = SessionViewModel(tasknode)
            self.set_view_model(new_view_model)                 

    def set_view_model(self, view_model: SessionViewModel):
        if self.view_model:
            self.view_model.streaming_update.disconnect(self.streaming_update)

        self.view_model = view_model
        if self.view_model:
            self.view_model.streaming_update.connect(self.streaming_update)
        self.update_session_view()

    def get_task(self):
        return self._task

    def update_session_view(self):
        # Clear existing widgets
        for i in reversed(range(self.scroll_layout.count())): 
            widget = self.scroll_layout.itemAt(i).widget()
            if widget:
                self.scroll_layout.removeWidget(widget)
                widget.deleteLater()

        # Add new widgets
        if self.view_model:
            for entry in self.view_model.get_entries():
                if DEBUG_ALL_PROMPTS or entry.include_in_display:
                    entry_widget = SessionEntryWidget(entry)
                    self.scroll_layout.addWidget(entry_widget)

        #
        self.scroll_to_bottom()

    def streaming_update(self):
        num_session_entries = len(self.view_model.get_entries())
        num_ui_entries = self.scroll_layout.count()
        if num_ui_entries > 0 and num_ui_entries == num_session_entries:
            last_widget = self.scroll_layout.itemAt(num_ui_entries-1).widget()
            last_widget.RefreshContent()
        elif num_ui_entries == num_session_entries-1:
            entry = self.view_model.get_entries()[-1]
            entry_widget = SessionEntryWidget(entry)
            self.scroll_layout.addWidget(entry_widget)
        else:
            self.update_session_view()
        
        #
        self.scroll_to_bottom()

    def send_message(self):
        if self.view_model:
            message = self.input_area.toPlainText().strip()
            if message:
                self.view_model.send_message(message)
                self.input_area.clear()

    def updateWidth(self):
        if self.parent():
            parent_width = self.parent().width()
            self.scroll_content.setMinimumWidth(parent_width)
            self.scroll_content.setMaximumWidth(parent_width)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.updateWidth()
        # this was a call to scroll_to_bottom, but that was causing the app to close at startup ?
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())

    def scroll_to_bottom(self):
        self.scroll_area.verticalScrollBar().setValue(self.scroll_area.verticalScrollBar().maximum())
        QApplication.processEvents()  # Force UI redraw  

class PropertiesWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)
        self.current_object = None

    def set_object(self, obj):
        self.current_object = obj
        self.clear_layout()
        
        if isinstance(obj, ISerializable):
            properties = obj.get_properties()
            for prop_name, prop_value in properties.items():
                read_only = obj.is_property_readonly(prop_name)
                label = QLabel(prop_name.capitalize())
                self.layout.addWidget(label)
                
                if isinstance(prop_value, str):
                    widget = QLineEdit(prop_value)
                    widget.textChanged.connect(lambda text, name=prop_name: self.update_property(name, text))
                elif isinstance(prop_value, int):
                    widget = QLineEdit(str(prop_value))
                    widget.textChanged.connect(lambda text, name=prop_name: self.update_property(name, int(text) if text.isdigit() else 0))
                elif isinstance(prop_value, float):
                    widget = QLineEdit(str(prop_value))
                    widget.textChanged.connect(lambda text, name=prop_name: self.update_property(name, float(text) if text.replace('.', '').isdigit() else 0.0))
                else:
                    widget = QLineEdit(str(prop_value))
                    widget.textChanged.connect(lambda text, name=prop_name: self.update_property(name, text))
                
                widget.setStyleSheet("QLineEdit[readOnly=\"true\"] {color: #808080; background-color: #F0F0F0;}")
                if read_only:
                    widget.setReadOnly(read_only)
                    
                self.layout.addWidget(widget)
            
            self.layout.addStretch()

    def update_property(self, name: str, value):
        if self.current_object:
            self.current_object.set_property(name, value)

    def clear_layout(self):
        while self.layout.count():
            item = self.layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()

