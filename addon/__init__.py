from PyQt5.Qt import Qt, QCheckBox, QLabel, QHBoxLayout, QLineEdit
from aqt.forms import preferences
from anki.hooks import wrap, addHook
import aqt
import anki.consts
import anki.sync

DEFAULT_ADDR = "http://localhost:27701/"
config = aqt.mw.addonManager.getConfig(__name__)

# TODO: force the user to log out before changing any of the settings

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

	pconfig = getprofileconfig()
	if pconfig["enabled"]:
		self.useCustomServer.setCheckState(Qt.Checked)
	if pconfig["addr"]:
		self.customServerAddr.setText(pconfig["addr"])

	self.customServerAddr.textChanged.connect(lambda text: updateserver(self, text))
	def onchecked(state):
		pconfig["enabled"] = state == Qt.Checked
		updateui(self, state)
		updateserver(self, self.customServerAddr.text())
	self.useCustomServer.stateChanged.connect(onchecked)

	updateui(self, self.useCustomServer.checkState())

def updateserver(self, text):
	pconfig = getprofileconfig()
	if pconfig['enabled']:
		addr = text or self.customServerAddr.placeholderText()
		pconfig['addr'] = addr
	setserver()
	aqt.mw.addonManager.writeConfig(__name__, config)

def updateui(self, state):
	self.serverAddrLabel.setEnabled(state == Qt.Checked)
	self.customServerAddr.setEnabled(state == Qt.Checked)

def setserver():
	pconfig = getprofileconfig()
	if pconfig['enabled']:
		aqt.mw.pm.profile['hostNum'] = None
		anki.sync.SYNC_BASE = "%s" + pconfig['addr']
	else:
		anki.sync.SYNC_BASE = anki.consts.SYNC_BASE

def getprofileconfig():
	if aqt.mw.pm.name not in config["profiles"]:
		# inherit global settings if present (used in earlier versions of the addon)
		config["profiles"][aqt.mw.pm.name] = {
			"enabled": config.get("enabled", False),
			"addr": config.get("addr", DEFAULT_ADDR),
		}
		aqt.mw.addonManager.writeConfig(__name__, config)
	return config["profiles"][aqt.mw.pm.name]

addHook("profileLoaded", setserver)
aqt.preferences.Preferences.__init__ = wrap(aqt.preferences.Preferences.__init__, addui, "after")
