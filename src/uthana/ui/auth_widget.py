"""Authentication and configuration widget."""

from uthana.core import client, config
from uthana.core.logger import logger
from uthana.ui import QtWidgets
from uthana.ui.collapsible_section import CollapsibleSection
from uthana.ui.workers import ApiWorker


class AuthWidget(CollapsibleSection):
    """API key entry, connection test, and account info display."""

    def __init__(self, parent=None):
        super().__init__("Config", parent=parent, collapsed=True)

        layout = self.content_layout()

        # API Key
        layout.addWidget(QtWidgets.QLabel("API Key:"))
        self.api_key_input = QtWidgets.QLineEdit()
        self.api_key_input.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key_input.setPlaceholderText("Enter your Uthana API key")
        layout.addWidget(self.api_key_input)

        # Domain
        layout.addWidget(QtWidgets.QLabel("Domain:"))
        self.domain_input = QtWidgets.QLineEdit()
        self.domain_input.setText("uthana.com")
        layout.addWidget(self.domain_input)

        # Buttons row
        btn_layout = QtWidgets.QHBoxLayout()
        self.test_btn = QtWidgets.QPushButton("Test connection")
        self.test_btn.clicked.connect(self._on_test_connection)
        btn_layout.addWidget(self.test_btn)

        self.save_btn = QtWidgets.QPushButton("Save")
        self.save_btn.clicked.connect(self._on_save_config)
        btn_layout.addWidget(self.save_btn)

        self.load_btn = QtWidgets.QPushButton("Load")
        self.load_btn.clicked.connect(self._on_load_config)
        btn_layout.addWidget(self.load_btn)

        layout.addLayout(btn_layout)

        # Account info section
        self.account_group = QtWidgets.QGroupBox("Account")
        account_layout = QtWidgets.QVBoxLayout(self.account_group)
        self.user_label = QtWidgets.QLabel("User: -")
        self.org_label = QtWidgets.QLabel("Organization: -")
        self.quota_label = QtWidgets.QLabel("Download quota: -")
        account_layout.addWidget(self.user_label)
        account_layout.addWidget(self.org_label)
        account_layout.addWidget(self.quota_label)
        layout.addWidget(self.account_group)
        self.account_group.setVisible(False)

        # Status
        self.status_label = QtWidgets.QLabel("")
        layout.addWidget(self.status_label)

        # Worker
        self._worker = None

        # Load saved config
        self._load_saved_config()

    def get_api_key(self):
        return self.api_key_input.text().strip()

    def get_domain(self):
        return self.domain_input.text().strip() or "uthana.com"

    def _load_saved_config(self):
        """Load previously saved configuration."""
        try:
            cfg = config.load_config()
            if cfg.auth.api_key:
                self.api_key_input.setText(cfg.auth.api_key)
            if cfg.auth.domain:
                self.domain_input.setText(cfg.auth.domain)
        except Exception as e:
            logger.warning("Failed to load saved config: %s", e)

    def _on_test_connection(self):
        api_key = self.get_api_key()
        domain = self.get_domain()

        if not api_key:
            self.status_label.setText("API Key is required")
            return

        self.test_btn.setEnabled(False)
        self.status_label.setText("Testing connection...")

        self._worker = ApiWorker(client.get_user_info, api_key, domain)
        self._worker.finished.connect(lambda r: self._on_user_info(r, api_key, domain))
        self._worker.error.connect(self._on_connection_error)
        self._worker.start()

    def _on_user_info(self, result, api_key, domain):
        self.test_btn.setEnabled(True)

        if result.success:
            user_data = result.data.get("user", {})
            user_name = user_data.get("name", "Unknown")
            self.user_label.setText(f"User: {user_name}")
            self.status_label.setText(f"Connected as: {user_name}")
            self.account_group.setVisible(True)

            # Fetch org info
            self._org_worker = ApiWorker(client.get_org_info, api_key, domain)
            self._org_worker.finished.connect(self._on_org_info)
            self._org_worker.start()
        else:
            self.status_label.setText(f"Connection failed: {result.message}")

    def _on_org_info(self, result):
        if result.success:
            org_data = result.data.get("org", {})
            self.org_label.setText(f"Organization: {org_data.get('name', '-')}")
            remaining = org_data.get("motion_download_secs_per_month_remaining", 0)
            self.quota_label.setText(f"Download quota: {remaining:.1f}s remaining")

    def _on_connection_error(self, error_msg):
        self.test_btn.setEnabled(True)
        self.status_label.setText(f"Error: {error_msg}")

    def _on_save_config(self):
        cfg = config.load_config()
        cfg.auth.api_key = self.get_api_key()
        cfg.auth.domain = self.get_domain()
        result = config.save_config(cfg)
        self.status_label.setText(
            "Config saved" if result.success else f"Save failed: {result.message}"
        )

    def _on_load_config(self):
        self._load_saved_config()
        self.status_label.setText("Config loaded")

    def get_download_secs_remaining(self):
        """Get the download seconds remaining text for other widgets to use."""
        text = self.quota_label.text()
        try:
            return float(text.split(":")[1].replace("s remaining", "").strip())
        except (IndexError, ValueError):
            return 0
