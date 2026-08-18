#!/usr/bin/env python3
"""
Terminal application for COM port communication with PySide6 GUI.
Standard interface similar to popular serial terminal programs.
"""

import sys
import serial
import serial.tools.list_ports
from datetime import datetime
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QComboBox, QPushButton, QLabel, QSpinBox, QGroupBox,
    QFormLayout, QStatusBar, QMessageBox, QSplitter, QCheckBox
)
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtGui import QFont, QTextCursor


class SerialWorker(QThread):
    """Worker thread for serial communication."""
    data_received = Signal(str)
    error_occurred = Signal(str)
    connected = Signal(bool)

    def __init__(self):
        super().__init__()
        self.serial_port = None
        self.is_running = False
        self.port_name = ""
        self.baudrate = 9600

    def run(self):
        """Main thread loop for reading serial data."""
        while self.is_running:
            try:
                if self.serial_port and self.serial_port.is_open:
                    if self.serial_port.in_waiting > 0:
                        data = self.serial_port.read(self.serial_port.in_waiting).decode('utf-8', errors='replace')
                        self.data_received.emit(data)
                self.msleep(10)  # Small delay to prevent CPU overuse
            except Exception as e:
                self.error_occurred.emit(str(e))
                break

    def connect(self, port_name, baudrate):
        """Connect to serial port."""
        try:
            self.port_name = port_name
            self.baudrate = baudrate
            self.serial_port = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.1
            )
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
        self.serial_port = None
        self.connected.emit(False)

    def send_data(self, data):
        """Send data through serial port."""
        if self.serial_port and self.serial_port.is_open:
            try:
                self.serial_port.write(data.encode('utf-8'))
            except Exception as e:
                self.error_occurred.emit(f"Send error: {str(e)}")


class SerialTerminal(QMainWindow):
    """Main window of the serial terminal application."""

    def __init__(self):
        super().__init__()
        self.worker = SerialWorker()
        self.init_ui()
        self.setup_connections()
        self.update_port_list()

    def init_ui(self):
        """Initialize the user interface."""
        self.setWindowTitle("Serial Terminal")
        self.setMinimumSize(800, 600)

        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Connection settings group
        connection_group = QGroupBox("Connection Settings")
        connection_layout = QFormLayout(connection_group)

        # Port selection
        self.port_combo = QComboBox()
        self.port_combo.setEditable(False)
        refresh_btn = QPushButton("🔄")
        refresh_btn.setFixedWidth(40)
        refresh_btn.clicked.connect(self.update_port_list)

        port_layout = QHBoxLayout()
        port_layout.addWidget(self.port_combo)
        port_layout.addWidget(refresh_btn)
        connection_layout.addRow("Port:", port_layout)

        # Baud rate selection
        self.baud_combo = QComboBox()
        self.baud_combo.addItems([
            "1200", "2400", "4800", "9600", "19200", "38400", 
            "57600", "115200", "230400", "460800", "921600"
        ])
        self.baud_combo.setCurrentText("9600")
        connection_layout.addRow("Baud Rate:", self.baud_combo)

        # Connection buttons
        button_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setCheckable(True)
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.clicked.connect(self.clear_terminal)

        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.clear_btn)
        button_layout.addStretch()
        connection_layout.addRow(button_layout)

        main_layout.addWidget(connection_group)

        # Terminal display area with splitter
        splitter = QSplitter(Qt.Vertical)

        # Output text area
        output_group = QGroupBox("Terminal Output")
        output_layout = QVBoxLayout(output_group)
        
        self.output_text = QTextEdit()
        self.output_text.setReadOnly(True)
        self.output_text.setFont(QFont("Consolas", 10))
        self.output_text.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        
        output_layout.addWidget(self.output_text)
        splitter.addWidget(output_group)

        # Input area
        input_group = QGroupBox("Send Data")
        input_layout = QVBoxLayout(input_group)

        self.input_text = QTextEdit()
        self.input_text.setMaximumHeight(100)
        self.input_text.setFont(QFont("Consolas", 10))
        self.input_text.setPlaceholderText("Enter data to send...")
        
        input_layout.addWidget(self.input_text)

        # Send options
        options_layout = QHBoxLayout()
        
        self.newline_check = QCheckBox("Append Newline (\\n)")
        self.newline_check.setChecked(True)
        
        self.hex_check = QCheckBox("Hex Mode")
        self.hex_check.setChecked(False)

        send_btn = QPushButton("Send")
        send_btn.clicked.connect(self.send_data)

        options_layout.addWidget(self.newline_check)
        options_layout.addWidget(self.hex_check)
        options_layout.addStretch()
        options_layout.addWidget(send_btn)

        input_layout.addLayout(options_layout)
        splitter.addWidget(input_group)

        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        main_layout.addWidget(splitter)

        # Status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_label = QLabel("Disconnected")
        self.status_bar.addWidget(self.status_label)

        # Timer for updating connection status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)

    def setup_connections(self):
        """Setup signal-slot connections."""
        self.worker.data_received.connect(self.append_output)
        self.worker.error_occurred.connect(self.show_error)
        self.worker.connected.connect(self.on_connection_changed)

    def update_port_list(self):
        """Update the list of available COM ports."""
        current_port = self.port_combo.currentText()
        self.port_combo.clear()
        
        ports = serial.tools.list_ports.comports()
        for port in ports:
            self.port_combo.addItem(f"{port.device} - {port.description}")
        
        # Try to restore previous selection
        index = self.port_combo.findText(current_port)
        if index >= 0:
            self.port_combo.setCurrentIndex(index)

    def toggle_connection(self):
        """Toggle connection state."""
        if self.connect_btn.isChecked():
            self.connect()
        else:
            self.disconnect()

    def connect(self):
        """Connect to serial port."""
        port_info = self.port_combo.currentText()
        if not port_info:
            self.show_error("No port selected")
            return
        
        port_name = port_info.split(" - ")[0]
        baudrate = int(self.baud_combo.currentText())
        
        self.connect_btn.setEnabled(False)
        self.worker.connect(port_name, baudrate)

    def disconnect(self):
        """Disconnect from serial port."""
        self.worker.disconnect()

    @Slot(bool)
    def on_connection_changed(self, connected):
        """Handle connection state change."""
        self.connect_btn.setEnabled(True)
        if connected:
            self.connect_btn.setText("Disconnect")
            self.connect_btn.setChecked(True)
            port_info = self.port_combo.currentText()
            baudrate = self.baud_combo.currentText()
            self.status_label.setText(f"Connected: {port_info} @ {baudrate} baud")
            self.append_output(f"\n--- Connected to {port_info} @ {baudrate} baud ---\n")
        else:
            self.connect_btn.setText("Connect")
            self.connect_btn.setChecked(False)
            self.status_label.setText("Disconnected")
            if self.worker.serial_port is None:
                self.append_output("\n--- Disconnected ---\n")

    @Slot(str)
    def append_output(self, data):
        """Append received data to output."""
        timestamp = datetime.now().strftime("[%H:%M:%S] ")
        self.output_text.moveCursor(QTextCursor.End)
        self.output_text.insertPlainText(timestamp + data)
        self.output_text.verticalScrollBar().setValue(
            self.output_text.verticalScrollBar().maximum()
        )

    @Slot(str)
    def show_error(self, error_message):
        """Show error message."""
        QMessageBox.critical(self, "Error", error_message)
        self.append_output(f"\n[ERROR] {error_message}\n")
        if self.connect_btn.isChecked():
            self.connect_btn.setChecked(False)
            self.connect_btn.setText("Connect")

    def send_data(self):
        """Send data through serial port."""
        data = self.input_text.toPlainText()
        if not data:
            return
        
        if self.newline_check.isChecked():
            data += "\n"
        
        if self.hex_check.isChecked():
            try:
                # Convert hex string to bytes
                hex_data = data.replace(" ", "").replace("\n", "")
                bytes_data = bytes.fromhex(hex_data)
                self.worker.send_data(bytes_data.decode('latin-1'))
            except ValueError:
                self.show_error("Invalid hex format")
                return
        else:
            self.worker.send_data(data)
        
        self.append_output(f"[TX] {data}")
        self.input_text.clear()

    def clear_terminal(self):
        """Clear the terminal output."""
        self.output_text.clear()

    def update_status(self):
        """Update connection status."""
        if self.worker.serial_port and self.worker.serial_port.is_open:
            rx_count = self.worker.serial_port.in_waiting
            self.status_label.setText(f"{self.status_label.text().split('@')[0]}@ {self.baud_combo.currentText()} baud | RX: {rx_count}")
        elif not self.connect_btn.isChecked():
            self.status_label.setText("Disconnected")

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
