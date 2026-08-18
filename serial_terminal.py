#!/usr/bin/env python3
"""
Terminal application for COM port communication with PySide6 GUI.
Full-featured interface inspired by classic terminal programs from 2000s
(HyperTerminal, PuTTY, Tera Term, RealTerm).
"""

import sys
import serial
import serial.tools.list_ports
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QComboBox, QPushButton, QLabel, QSpinBox, QGroupBox,
    QFormLayout, QStatusBar, QMessageBox, QSplitter, QCheckBox,
    QTabWidget, QToolBar, QFileDialog,
    QDialog, QDialogButtonBox, QListWidget, QListWidgetItem, QRadioButton,
    QButtonGroup, QFrame, QLineEdit, QGridLayout, QProgressBar,
    QInputDialog
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer, QFile, QTextStream, QUrl
from PySide6.QtGui import QFont, QTextCursor, QColor, QPalette, QKeySequence, QIcon, QAction, QDesktopServices, QShortcut


class SerialWorker(QThread):
    """Worker thread for serial communication."""
    data_received = Signal(str)
    data_received_hex = Signal(bytes)
    error_occurred = Signal(str)
    connected = Signal(bool)
    status_update = Signal(int, int)  # rx_count, tx_count

    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.is_running = False
        self.port_name = ""
        self.baudrate = 9600
        self.bytesize = serial.EIGHTBITS
        self.parity = serial.PARITY_NONE
        self.stopbits = serial.STOPBITS_ONE
        self.rx_count = 0
        self.tx_count = 0
        self.log_file = None
        self.logging_enabled = False

    def run(self):
        """Main thread loop for reading serial data."""
        while self.is_running:
            try:
                if self.serial_port and self.serial_port.is_open:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting)
                        self.rx_count += len(data)
                        
                        # Try to decode as UTF-8, fallback to latin-1
                        try:
                            text_data = data.decode('utf-8')
                        except UnicodeDecodeError:
                            text_data = data.decode('latin-1', errors='replace')
                        
                        self.data_received.emit(text_data)
                        self.data_received_hex.emit(data)
                        
                        # Log to file if enabled
                        if self.logging_enabled and self.log_file:
                            self.log_file.write(data)
                            self.log_file.flush()
                    
                    self.status_update.emit(self.rx_count, self.tx_count)
                self.msleep(10)
            except Exception as e:
                self.error_occurred.emit(str(e))
                break

    def connect(self, port_name, baudrate, bytesize, parity, stopbits):
        """Connect to serial port."""
        try:
            self.port_name = port_name
            self.baudrate = baudrate
            self.bytesize = bytesize
            self.parity = parity
            self.stopbits = stopbits
            
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=bytesize,
                parity=parity,
                stopbits=stopbits,
                timeout=0.1
            )
            self.rx_count = 0
            self.tx_count = 0
            self.is_running = True
            self.start()
            self.connected.emit(True)
        except Exception as e:
            self.error_occurred.emit(f"Connection error: {str(e)}")
            self.connected.emit(False)

    def disconnect(self):
        """Disconnect from serial port."""
        self.is_running = False
        if self.isRunning():
            self.wait(1000)
        if self.serial_port and self.serial_port.is_open:
            self.serial_port.close()
        if self.log_file:
            self.log_file.close()
            self.log_file = None
        self.serial_port = None
        self.connected.emit(False)

    def send_data(self, data):
        """Send data through serial port."""
        if self.serial_port and self.serial_port.is_open:
            try:
                if isinstance(data, str):
                    data_bytes = data.encode('utf-8')
                else:
                    data_bytes = data
                self.serial_port.write(data_bytes)
                self.tx_count += len(data_bytes)
                self.status_update.emit(self.rx_count, self.tx_count)
            except Exception as e:
                self.error_occurred.emit(f"Send error: {str(e)}")

    def enable_logging(self, filename):
        """Enable logging to file."""
        try:
            if self.log_file:
                self.log_file.close()
            self.log_file = open(filename, 'ab')
            self.logging_enabled = True
        except Exception as e:
            self.error_occurred.emit(f"Log file error: {str(e)}")
            self.logging_enabled = False

    def disable_logging(self):
        """Disable logging."""
        self.logging_enabled = False
        if self.log_file:
            self.log_file.close()
            self.log_file = None

    def get_counts(self):
        """Get RX/TX counts."""
        return self.rx_count, self.tx_count


class SettingsDialog(QDialog):
    """Dialog for advanced serial port settings."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Port Settings")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        layout = QVBoxLayout(self)
        
        # Data bits
        data_group = QGroupBox("Data Bits")
        data_layout = QHBoxLayout(data_group)
        self.data_bits_group = QButtonGroup(self)
        for i, bits in enumerate([5, 6, 7, 8]):
            rb = QRadioButton(f"{bits} bits")
            self.data_bits_group.addButton(rb, i)
            data_layout.addWidget(rb)
            if bits == 8:
                rb.setChecked(True)
        layout.addWidget(data_group)
        
        # Parity
        parity_group = QGroupBox("Parity")
        parity_layout = QHBoxLayout(parity_group)
        self.parity_group = QButtonGroup(self)
        parity_options = [
            (serial.PARITY_NONE, "None"),
            (serial.PARITY_EVEN, "Even"),
            (serial.PARITY_ODD, "Odd"),
            (serial.PARITY_MARK, "Mark"),
            (serial.PARITY_SPACE, "Space")
        ]
        for i, (value, label) in enumerate(parity_options):
            rb = QRadioButton(label)
            self.parity_group.addButton(rb, i)
            parity_layout.addWidget(rb)
            if value == serial.PARITY_NONE:
                rb.setChecked(True)
        layout.addWidget(parity_group)
        
        # Stop bits
        stop_group = QGroupBox("Stop Bits")
        stop_layout = QHBoxLayout(stop_group)
        self.stop_bits_group = QButtonGroup(self)
        stop_options = [
            (serial.STOPBITS_ONE, "1"),
            (serial.STOPBITS_ONE_POINT_FIVE, "1.5"),
            (serial.STOPBITS_TWO, "2")
        ]
        for i, (value, label) in enumerate(stop_options):
            rb = QRadioButton(f"{label} stop bit(s)")
            self.stop_bits_group.addButton(rb, i)
            stop_layout.addWidget(rb)
            if value == serial.STOPBITS_ONE:
                rb.setChecked(True)
        layout.addWidget(stop_group)
        
        # Flow control (informational only - pyserial handles automatically)
        flow_group = QGroupBox("Flow Control")
        flow_layout = QHBoxLayout(flow_group)
        flow_label = QLabel("Hardware (RTS/CTS) and Software (XON/XOFF) flow control are supported")
        flow_label.setWordWrap(True)
        flow_layout.addWidget(flow_label)
        layout.addWidget(flow_group)
        
        layout.addStretch()
        
        # Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def get_settings(self):
        """Get selected settings."""
        data_bits_map = [5, 6, 7, 8]
        parity_map = [serial.PARITY_NONE, serial.PARITY_EVEN, serial.PARITY_ODD, 
                     serial.PARITY_MARK, serial.PARITY_SPACE]
        stop_bits_map = [serial.STOPBITS_ONE, serial.STOPBITS_ONE_POINT_FIVE, serial.STOPBITS_TWO]
        
        return {
            'bytesize': data_bits_map[self.data_bits_group.checkedId()],
            'parity': parity_map[self.parity_group.checkedId()],
            'stopbits': stop_bits_map[self.stop_bits_group.checkedId()]
        }


class SerialTerminal(QMainWindow):
    """Main window of the serial terminal application."""

    def __init__(self):
        super().__init__()
        self.worker = SerialWorker()
        self.log_file_path = None
        self.init_ui()
        self.setup_connections()
        self.update_port_list()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Serial Terminal Pro")
        self.setMinimumSize(1024, 768)
        
        # Create menu bar
        self.create_menu_bar()
        
        # Create toolbar
        self.create_toolbar()

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(5)

        # Connection toolbar group
        connection_group = QGroupBox("Connection")
        connection_layout = QGridLayout(connection_group)
        connection_layout.setSpacing(5)

        # Port selection
        connection_layout.addWidget(QLabel("Port:"), 0, 0)
        self.port_combo = QComboBox()
        self.port_combo.setEditable(False)
        self.port_combo.setMinimumWidth(200)
        refresh_btn = QPushButton("↻")
        refresh_btn.setToolTip("Refresh port list")
        refresh_btn.setFixedWidth(35)
        refresh_btn.clicked.connect(self.update_port_list)
        
        port_frame = QFrame()
        port_layout = QHBoxLayout(port_frame)
        port_layout.setContentsMargins(0, 0, 0, 0)
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(refresh_btn)
        connection_layout.addWidget(port_frame, 0, 1)

        # Baud rate selection
        connection_layout.addWidget(QLabel("Baud:"), 0, 2)
        self.baud_combo = QComboBox()
        self.baud_combo.setEditable(True)
        self.baud_combo.addItems([
            "1200", "2400", "4800", "9600", "19200", "38400", 
            "57600", "115200", "230400", "460800", "921600", "1000000"
        ])
        self.baud_combo.setCurrentText("9600")
        self.baud_combo.setMinimumWidth(100)
        connection_layout.addWidget(self.baud_combo, 0, 3)

        # Settings button
        self.settings_btn = QPushButton("Settings...")
        self.settings_btn.setToolTip("Advanced port settings (data bits, parity, stop bits)")
        self.settings_btn.clicked.connect(self.show_settings)
        connection_layout.addWidget(self.settings_btn, 0, 4)

        # Connection buttons
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setCheckable(True)
        self.connect_btn.setMinimumWidth(80)
        self.connect_btn.clicked.connect(self.toggle_connection)
        connection_layout.addWidget(self.connect_btn, 0, 5)
        
        self.disconnect_btn = QPushButton("Disconnect")
        self.disconnect_btn.setEnabled(False)
        self.disconnect_btn.setMinimumWidth(80)
        self.disconnect_btn.clicked.connect(self.disconnect)
        connection_layout.addWidget(self.disconnect_btn, 0, 6)

        main_layout.addWidget(connection_group)

        # Main splitter with tabs
        main_splitter = QSplitter(Qt.Horizontal)
        
        # Left side - Terminal area
        terminal_widget = QWidget()
        terminal_layout = QVBoxLayout(terminal_widget)
        terminal_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget for different views
        self.tabs = QTabWidget()
        
        # Text view tab
        text_view_widget = QWidget()
        text_view_layout = QVBoxLayout(text_view_widget)
        text_view_layout.setContentsMargins(0, 0, 0, 0)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.output_text.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.output_text.setAcceptRichText(False)
        text_view_layout.addWidget(self.output_text)
        
        self.tabs.addTab(text_view_widget, "Text View")
        
        # Hex view tab
        hex_view_widget = QWidget()
        hex_view_layout = QVBoxLayout(hex_view_widget)
        hex_view_layout.setContentsMargins(0, 0, 0, 0)
        
        self.hex_output = QTextEdit()
        self.hex_output.setReadOnly(True)
        self.hex_output.setFont(QFont("Consolas", 9))
        self.hex_output.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        hex_view_layout.addWidget(self.hex_output)
        
        self.tabs.addTab(hex_view_widget, "Hex View")
        
        terminal_layout.addWidget(self.tabs)
        
        # Input area
        input_group = QGroupBox("Transmit")
        input_layout = QVBoxLayout(input_group)
        
        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(80)
        self.input_text.setFont(QFont("Consolas", 10))
        self.input_text.setPlaceholderText("Enter data to send (Press Ctrl+Enter to send)")
        input_layout.addWidget(self.input_text)

        # Transmit options
        options_layout = QHBoxLayout()
        
        self.newline_check = QCheckBox("Append LF")
        self.newline_check.setChecked(False)
        
        self.cr_check = QCheckBox("Append CR")
        self.cr_check.setChecked(False)
        
        self.hex_tx_check = QCheckBox("Hex Mode")
        self.hex_tx_check.setChecked(False)
        
        self.echo_check = QCheckBox("Local Echo")
        self.echo_check.setChecked(False)
        
        options_layout.addWidget(self.newline_check)
        options_layout.addWidget(self.cr_check)
        options_layout.addWidget(self.hex_tx_check)
        options_layout.addWidget(self.echo_check)
        options_layout.addStretch()

        input_layout.addLayout(options_layout)
        
        # Send buttons row
        send_layout = QHBoxLayout()
        
        self.send_btn = QPushButton("Send")
        self.send_btn.setMinimumWidth(80)
        self.send_btn.clicked.connect(self.send_data)
        send_layout.addWidget(self.send_btn)
        
        self.send_file_btn = QPushButton("Send File...")
        self.send_file_btn.clicked.connect(self.send_file)
        send_layout.addWidget(self.send_file_btn)
        
        self.clear_rx_btn = QPushButton("Clear RX")
        self.clear_rx_btn.clicked.connect(self.clear_rx)
        send_layout.addWidget(self.clear_rx_btn)
        
        send_layout.addStretch()
        
        input_layout.addLayout(send_layout)
        
        main_splitter.addWidget(terminal_widget)
        
        # Right side - Control panel
        control_widget = QWidget()
        control_layout = QVBoxLayout(control_widget)
        control_layout.setContentsMargins(0, 0, 0, 0)
        
        # Status group
        status_group = QGroupBox("Connection Status")
        status_layout = QFormLayout(status_group)
        
        self.status_port_label = QLabel("-")
        status_layout.addRow("Port:", self.status_port_label)
        
        self.status_baud_label = QLabel("-")
        status_layout.addRow("Baud:", self.status_baud_label)
        
        self.status_bytesize_label = QLabel("-")
        status_layout.addRow("Data:", self.status_bytesize_label)
        
        self.status_parity_label = QLabel("-")
        status_layout.addRow("Parity:", self.status_parity_label)
        
        self.status_stopbits_label = QLabel("-")
        status_layout.addRow("Stop:", self.status_stopbits_label)
        
        control_layout.addWidget(status_group)
        
        # Traffic group
        traffic_group = QGroupBox("Traffic Counter")
        traffic_layout = QVBoxLayout(traffic_group)
        
        self.rx_label = QLabel("RX: 0 bytes")
        self.rx_label.setFont(QFont("Consolas", 11))
        traffic_layout.addWidget(self.rx_label)
        
        self.tx_label = QLabel("TX: 0 bytes")
        self.tx_label.setFont(QFont("Consolas", 11))
        traffic_layout.addWidget(self.tx_label)
        
        self.reset_counter_btn = QPushButton("Reset Counters")
        self.reset_counter_btn.clicked.connect(self.reset_counters)
        traffic_layout.addWidget(self.reset_counter_btn)
        
        traffic_layout.addStretch()
        
        control_layout.addWidget(traffic_group)
        
        # Logging group
        log_group = QGroupBox("Session Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_check = QCheckBox("Enable Logging")
        self.log_check.stateChanged.connect(self.toggle_logging)
        log_layout.addWidget(self.log_check)
        
        self.log_path_label = QLabel("No log file selected")
        self.log_path_label.setWordWrap(True)
        log_layout.addWidget(self.log_path_label)
        
        log_btn_layout = QHBoxLayout()
        self.log_select_btn = QPushButton("Select Log File...")
        self.log_select_btn.clicked.connect(self.select_log_file)
        log_btn_layout.addWidget(self.log_select_btn)
        
        self.log_open_btn = QPushButton("Open Log")
        self.log_open_btn.clicked.connect(self.open_log_folder)
        log_btn_layout.addWidget(self.log_open_btn)
        
        log_layout.addLayout(log_btn_layout)
        
        control_layout.addWidget(log_group)
        
        # Quick commands group
        cmd_group = QGroupBox("Quick Commands")
        cmd_layout = QVBoxLayout(cmd_group)
        
        self.cmd_list = QListWidget()
        self.cmd_list.setMaximumHeight(150)
        self.cmd_list.itemDoubleClicked.connect(self.send_quick_command)
        cmd_layout.addWidget(self.cmd_list)
        
        cmd_btn_layout = QHBoxLayout()
        add_cmd_btn = QPushButton("Add")
        add_cmd_btn.clicked.connect(self.add_command)
        cmd_btn_layout.addWidget(add_cmd_btn)
        
        del_cmd_btn = QPushButton("Delete")
        del_cmd_btn.clicked.connect(self.delete_command)
        cmd_btn_layout.addWidget(del_cmd_btn)
        
        edit_cmd_btn = QPushButton("Edit")
        edit_cmd_btn.clicked.connect(self.edit_command)
        cmd_btn_layout.addWidget(edit_cmd_btn)
        
        cmd_layout.addLayout(cmd_btn_layout)
        
        control_layout.addWidget(cmd_group)
        
        control_layout.addStretch()
        
        main_splitter.addWidget(control_widget)
        main_splitter.setStretchFactor(0, 3)
        main_splitter.setStretchFactor(1, 1)
        main_splitter.setCollapsible(1, False)

        main_layout.addWidget(main_splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        
        self.connection_status = QLabel("Disconnected")
        self.connection_status.setStyleSheet("color: red; font-weight: bold;")
        self.status_bar.addWidget(self.connection_status)
        
        self.traffic_status = QLabel("RX: 0 | TX: 0")
        self.status_bar.addWidget(self.traffic_status)
        
        self.port_info_status = QLabel("")
        self.status_bar.addPermanentWidget(self.port_info_status)
        
        # Shortcuts
        QShortcut(QKeySequence("Ctrl+Return"), self, self.send_data)
        QShortcut(QKeySequence("Ctrl+L"), self, self.clear_rx)
        QShortcut(QKeySequence("F5"), self, self.update_port_list)
        QShortcut(QKeySequence("Ctrl+S"), self, self.save_session)
        QShortcut(QKeySequence("Ctrl+O"), self, self.open_send_file)

        # Timer for updating connection status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_traffic_display)
        self.status_timer.start(500)
        
        # Store current port settings
        self.current_bytesize = serial.EIGHTBITS
        self.current_parity = serial.PARITY_NONE
        self.current_stopbits = serial.STOPBITS_ONE

    def create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu("&File")
        
        save_session_action = QAction("&Save Session", self)
        save_session_action.setShortcut(QKeySequence("Ctrl+S"))
        save_session_action.triggered.connect(self.save_session)
        file_menu.addAction(save_session_action)
        
        open_log_action = QAction("&Open Log Folder", self)
        open_log_action.triggered.connect(self.open_log_folder)
        file_menu.addAction(open_log_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction("E&xit", self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Connection menu
        conn_menu = menubar.addMenu("&Connection")
        
        connect_action = QAction("&Connect", self)
        connect_action.setShortcut(QKeySequence("Ctrl+C"))
        connect_action.triggered.connect(self.toggle_connection)
        conn_menu.addAction(connect_action)
        
        disconnect_action = QAction("&Disconnect", self)
        disconnect_action.setShortcut(QKeySequence("Ctrl+D"))
        disconnect_action.triggered.connect(self.disconnect)
        conn_menu.addAction(disconnect_action)
        
        conn_menu.addSeparator()
        
        settings_action = QAction("&Port Settings...", self)
        settings_action.triggered.connect(self.show_settings)
        conn_menu.addAction(settings_action)
        
        refresh_action = QAction("&Refresh Ports", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self.update_port_list)
        conn_menu.addAction(refresh_action)
        
        # View menu
        view_menu = menubar.addMenu("&View")
        
        clear_rx_action = QAction("Clear &RX Buffer", self)
        clear_rx_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_rx_action.triggered.connect(self.clear_rx)
        view_menu.addAction(clear_rx_action)
        
        clear_hex_action = QAction("Clear &Hex View", self)
        clear_hex_action.triggered.connect(self.clear_hex)
        view_menu.addAction(clear_hex_action)
        
        view_menu.addSeparator()
        
        text_view_action = QAction("&Text View", self)
        text_view_action.triggered.connect(lambda: self.tabs.setCurrentIndex(0))
        view_menu.addAction(text_view_action)
        
        hex_view_action = QAction("&Hex View", self)
        hex_view_action.triggered.connect(lambda: self.tabs.setCurrentIndex(1))
        view_menu.addAction(hex_view_action)
        
        # Tools menu
        tools_menu = menubar.addMenu("&Tools")
        
        send_file_action = QAction("Send &File...", self)
        send_file_action.setShortcut(QKeySequence("Ctrl+O"))
        send_file_action.triggered.connect(self.open_send_file)
        tools_menu.addAction(send_file_action)
        
        log_action = QAction("Enable/&Disable Logging", self)
        log_action.triggered.connect(lambda: self.log_check.setChecked(not self.log_check.isChecked()))
        tools_menu.addAction(log_action)
        
        # Help menu
        help_menu = menubar.addMenu("&Help")
        
        about_action = QAction("&About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def create_toolbar(self):
        """Create the main toolbar."""
        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        
        connect_tool_btn = QPushButton("Connect")
        connect_tool_btn.clicked.connect(self.toggle_connection)
        toolbar.addWidget(connect_tool_btn)
        
        toolbar.addSeparator()
        
        refresh_tool_btn = QPushButton("↻ Refresh")
        refresh_tool_btn.clicked.connect(self.update_port_list)
        toolbar.addWidget(refresh_tool_btn)
        
        toolbar.addSeparator()
        
        clear_tool_btn = QPushButton("Clear RX")
        clear_tool_btn.clicked.connect(self.clear_rx)
        toolbar.addWidget(clear_tool_btn)

    def setup_connections(self):
        """Setup signal-slot connections."""
        self.worker.data_received.connect(self.append_output)
        self.worker.data_received_hex.connect(self.append_hex_output)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.connected.connect(self.on_connection_changed)
        self.worker.status_update.connect(self.update_traffic)

    def update_port_list(self):
        """Update the list of available COM ports."""
        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        
        ports = serial.tools.list_ports.comports()
        for port in sorted(ports, key=lambda p: p.device):
            display_text = f"{port.device}"
            if port.description and port.description != "n/a":
                display_text += f" - {port.description}"
            self.port_combo.addItem(display_text)
        
        # Try to restore previous selection
        index = self.port_combo.findText(current_port)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)

    def toggle_connection(self):
        """Toggle connection state."""
        if self.connect_btn.isChecked():
            self.connect()
        else:
            self.disconnect_btn.click()

    def connect(self):
        """Connect to serial port."""
        port_info = self.port_combo.currentText()
        if not port_info:
            self.show_error("No port selected")
            return
        
        port_name = port_info.split(" - ")[0]
        baudrate = int(self.baud_combo.currentText())
        
        self.connect_btn.setEnabled(False)
        self.worker.connect(port_name, baudrate, self.current_bytesize, 
                           self.current_parity, self.current_stopbits)

    def disconnect(self):
        """Disconnect from serial port."""
        self.worker.disconnect()

    @Slot(bool)
    def on_connection_changed(self, connected):
        """Handle connection state change."""
        self.connect_btn.setEnabled(True)
        if connected:
            self.connect_btn.setText("Connected")
            self.connect_btn.setChecked(True)
            self.disconnect_btn.setEnabled(True)
            
            port_info = self.port_combo.currentText()
            port_name = port_info.split(" - ")[0]
            baudrate = self.baud_combo.currentText()
            
            self.connection_status.setText("Connected")
            self.connection_status.setStyleSheet("color: green; font-weight: bold;")
            
            self.status_port_label.setText(port_name)
            self.status_baud_label.setText(baudrate)
            self.status_bytesize_label.setText(str(self.current_bytesize))
            
            parity_str = {
                serial.PARITY_NONE: "None",
                serial.PARITY_EVEN: "Even",
                serial.PARITY_ODD: "Odd",
                serial.PARITY_MARK: "Mark",
                serial.PARITY_SPACE: "Space"
            }.get(self.current_parity, "Unknown")
            self.status_parity_label.setText(parity_str)
            
            stopbits_str = {
                serial.STOPBITS_ONE: "1",
                serial.STOPBITS_ONE_POINT_FIVE: "1.5",
                serial.STOPBITS_TWO: "2"
            }.get(self.current_stopbits, "Unknown")
            self.status_stopbits_label.setText(stopbits_str)
            
            self.port_info_status.setText(f"{port_name} @ {baudrate} baud, {self.current_bytesize}{parity_str[0]}{stopbits_str}")
            
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            self.output_text.append(f"\n{timestamp} --- Connected to {port_name} @ {baudrate} baud ---\n")
        else:
            self.connect_btn.setText("Connect")
            self.connect_btn.setChecked(False)
            self.disconnect_btn.setEnabled(False)
            self.connection_status.setText("Disconnected")
            self.connection_status.setStyleSheet("color: red; font-weight: bold;")
            self.status_port_label.setText("-")
            self.status_baud_label.setText("-")
            self.status_bytesize_label.setText("-")
            self.status_parity_label.setText("-")
            self.status_stopbits_label.setText("-")
            self.port_info_status.setText("")
            
            if self.worker.serial_port is None:
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                self.output_text.append(f"\n{timestamp} --- Disconnected ---\n")

    @Slot(str)
    def append_output(self, data):
        """Append received data to text output."""
        cursor = self.output_text.textCursor()
        cursor.movePosition(QTextCursor.End)
        
        lines = data.split('\n')
        for i, line in enumerate(lines):
            if i > 0:
                timestamp = datetime.now().strftime("[%H:%M:%S] ")
                cursor.insertPlainText(f"\n{timestamp}{line}")
            else:
                cursor.insertPlainText(line)
        
        self.output_text.setTextCursor(cursor)
        self.output_text.ensureCursorVisible()
        
        # Local echo if enabled
        if hasattr(self, 'echo_check') and self.echo_check.isChecked():
            pass  # Echo is handled separately for TX

    @Slot(bytes)
    def append_hex_output(self, data):
        """Append received data to hex output."""
        hex_lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            hex_part = ' '.join(f'{b:02X}' for b in chunk)
            ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
            offset = f'{i:08X}'
            hex_lines.append(f"{offset}  {hex_part:<48}  |{ascii_part}|")
        
        self.hex_output.append('\n'.join(hex_lines))

    @Slot(int, int)
    def update_traffic(self, rx_count, tx_count):
        """Update traffic counters."""
        self.rx_label.setText(f"RX: {rx_count:,} bytes")
        self.tx_label.setText(f"TX: {tx_count:,} bytes")
        self.traffic_status.setText(f"RX: {rx_count:,} | TX: {tx_count:,}")

    def update_traffic_display(self):
        """Periodically update traffic display."""
        if self.worker.serial_port and self.worker.serial_port.is_open:
            rx, tx = self.worker.get_counts()
            in_waiting = self.worker.serial_port.in_waiting
            self.traffic_status.setText(f"RX: {rx:,} | TX: {tx:,} | Buffer: {in_waiting}")

    @Slot(str)
    def show_error(self, error_message):
        """Show error message."""
        QMessageBox.critical(self, "Error", error_message)
        timestamp = datetime.now().strftime("[%H:%M:%S]")
        self.output_text.append(f"\n{timestamp} [ERROR] {error_message}\n")
        if self.connect_btn.isChecked():
            self.connect_btn.setChecked(False)
            self.connect_btn.setText("Connect")

    def send_data(self):
        """Send data through serial port."""
        data = self.input_text.toPlainText()
        if not data:
            return
        
        original_data = data
        
        if self.newline_check.isChecked():
            data += "\n"
        if self.cr_check.isChecked():
            data += "\r"
        
        if self.hex_tx_check.isChecked():
            try:
                hex_data = data.replace(" ", "").replace("\n", "").replace("\r", "")
                bytes_data = bytes.fromhex(hex_data)
                self.worker.send_data(bytes_data)
                if self.echo_check.isChecked():
                    self.output_text.append(f"[TX-HEX] {hex_data}")
            except ValueError:
                self.show_error("Invalid hex format. Use only hex digits (0-9, A-F).")
                return
        else:
            self.worker.send_data(data)
            if self.echo_check.isChecked():
                timestamp = datetime.now().strftime("[%H:%M:%S]")
                display_data = original_data.replace('\n', '\\n').replace('\r', '\\r')
                self.output_text.append(f"{timestamp} [TX] {display_data}")
        
        self.input_text.clear()

    def send_file(self):
        """Send a file through serial port."""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File to Send", "", "All Files (*)")
        if file_path:
            try:
                with open(file_path, 'rb') as f:
                    data = f.read()
                self.worker.send_data(data)
                self.output_text.append(f"[TX-FILE] Sent {len(data)} bytes from {file_path}")
            except Exception as e:
                self.show_error(f"Error sending file: {str(e)}")

    def open_send_file(self):
        """Open file dialog for sending."""
        self.send_file()

    def clear_rx(self):
        """Clear the RX buffer."""
        self.output_text.clear()
        self.reset_counters()

    def clear_hex(self):
        """Clear the hex view."""
        self.hex_output.clear()

    def reset_counters(self):
        """Reset traffic counters."""
        if self.worker.serial_port:
            self.worker.rx_count = 0
            self.worker.tx_count = 0
        self.update_traffic(0, 0)

    def show_settings(self):
        """Show advanced port settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec() == QDialog.Accepted:
            settings = dialog.get_settings()
            self.current_bytesize = settings['bytesize']
            self.current_parity = settings['parity']
            self.current_stopbits = settings['stopbits']

    def toggle_logging(self, state):
        """Toggle session logging."""
        if state == Qt.Checked:
            if self.log_file_path:
                self.worker.enable_logging(self.log_file_path)
                self.log_path_label.setText(f"Logging to: {self.log_file_path}")
            else:
                self.select_log_file()
        else:
            self.worker.disable_logging()
            self.log_path_label.setText("No log file selected")

    def select_log_file(self):
        """Select log file path."""
        default_name = f"serial_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.bin"
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Select Log File", default_name, "Binary Files (*.bin);;Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            self.log_file_path = file_path
            self.log_path_label.setText(f"Logging to: {file_path}")
            if self.log_check.isChecked():
                self.worker.enable_logging(file_path)

    def open_log_folder(self):
        """Open the folder containing log files."""
        if self.log_file_path:
            import os
            folder = os.path.dirname(self.log_file_path)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))
        else:
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.getcwd()))

    def add_command(self):
        """Add a quick command."""
        from PySide6.QtWidgets import QInputDialog
        cmd, ok = QInputDialog.getText(self, "Add Command", "Enter command name:")
        if ok and cmd:
            data, ok = QInputDialog.getText(self, "Command Data", "Enter data to send:")
            if ok and data:
                item = QListWidgetItem(f"{cmd}: {data[:30]}...")
                item.setData(Qt.UserRole, data)
                self.cmd_list.addItem(item)

    def delete_command(self):
        """Delete selected quick command."""
        current_item = self.cmd_list.currentItem()
        if current_item:
            row = self.cmd_list.row(current_item)
            self.cmd_list.takeItem(row)

    def edit_command(self):
        """Edit selected quick command."""
        from PySide6.QtWidgets import QInputDialog
        current_item = self.cmd_list.currentItem()
        if current_item:
            old_data = current_item.data(Qt.UserRole)
            new_data, ok = QInputDialog.getText(self, "Edit Command", "Enter new data:", text=old_data)
            if ok and new_data:
                current_item.setData(Qt.UserRole, new_data)
                cmd_text = current_item.text().split(':')[0]
                current_item.setText(f"{cmd_text}: {new_data[:30]}...")

    def send_quick_command(self, item):
        """Send a quick command."""
        data = item.data(Qt.UserRole)
        if data:
            self.input_text.setText(data)
            self.send_data()

    def save_session(self):
        """Save current session to file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Session", "", "Text Files (*.txt);;All Files (*)"
        )
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.output_text.toPlainText())
                self.status_bar.showMessage(f"Session saved to {file_path}", 3000)
            except Exception as e:
                self.show_error(f"Error saving session: {str(e)}")

    def show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Serial Terminal Pro",
            "<h3>Serial Terminal Pro</h3>"
            "<p>A full-featured serial terminal application inspired by classic "
            "terminal programs from the 2000s.</p>"
            "<p><b>Features:</b></p>"
            "<ul>"
            "<li>Text and Hex view modes</li>"
            "<li>Session logging</li>"
            "<li>Quick commands</li>"
            "<li>File transfer</li>"
            "<li>Traffic counters</li>"
            "</ul>"
            "<p>Built with PySide6 and pyserial.</p>"
        )

    def closeEvent(self, event):
        """Handle window close event."""
        if self.worker.is_running:
            self.worker.disconnect()
        event.accept()


def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    
    window = SerialTerminal()
    window.show()
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
