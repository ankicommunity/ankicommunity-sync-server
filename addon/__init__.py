from PyQt5.Qt import Qt, QCheckBox, QLabel, QHBoxLayout, QLineEdit
from aqt.forms import preferences
from anki.hooks import wrap
import aqt
import anki.consts
import anki.sync

ORIG_SYNC_BASE = anki.consts.SYNC_BASE
DEFAULT_ADDR = "http://localhost:27701/"
config = aqt.mw.addonManager.getConfig(__name__)

def addui(self, _):
	self = self.form
	parent_w = self.tab_2
	parent_l = self.vboxlayout
	self.useCustomServer = QCheckBox(parent_w)
	self.useCustomServer.setText("Use custom sync server")
	parent_l.addWidget(self.useCustomServer)
	cshl = QHBoxLayout()
	parent_l.addLayout(cshl)

	self.serverAddrLabel = QLabel(parent_w)
	self.serverAddrLabel.setText("Server address")
	cshl.addWidget(self.serverAddrLabel)
	self.customServerAddr = QLineEdit(parent_w)
	self.customServerAddr.setPlaceholderText(DEFAULT_ADDR)
	cshl.addWidget(self.customServerAddr)

	if config["enabled"]:
		self.useCustomServer.setCheckState(Qt.Checked)
	if config["addr"]:
		self.customServerAddr.setText(config['addr'])

	self.customServerAddr.textChanged.connect(lambda text: updateserver(self, text))
	def onchecked(state):
		config["enabled"] = state == Qt.Checked
		updateui(self, state)
		updateserver(self, self.customServerAddr.text())
	self.useCustomServer.stateChanged.connect(onchecked)

	updateui(self, self.useCustomServer.checkState())

def updateserver(self, text):
	if config['enabled']:
		addr = text or self.customServerAddr.placeholderText()
		config['addr'] = addr
		anki.consts.SYNC_BASE = addr + "%s"
	else:
		anki.consts.SYNC_BASE = ORIG_SYNC_BASE
	aqt.mw.addonManager.writeConfig(__name__, config)

def updateui(self, state):
	self.serverAddrLabel.setEnabled(state == Qt.Checked)
	self.customServerAddr.setEnabled(state == Qt.Checked)

if config['enabled']:
	anki.consts.SYNC_BASE = config['addr'] + "%s"
aqt.preferences.Preferences.__init__ = wrap(aqt.preferences.Preferences.__init__, addui, "after")
