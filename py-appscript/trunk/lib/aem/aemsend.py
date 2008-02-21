"""send -- Construct and send Apple events.

(C) 2005-2008 HAS
"""

from ae import AECreateAppleEvent, AECreateDesc, MacOSError
import kae

from aemcodecs import Codecs

__all__ = ['CommandError', 'Event']

######################################################################
# PRIVATE
######################################################################

_defaultCodecs = Codecs() # used to unpack application errors and, optionally, return values


######################################################################
# PUBLIC
######################################################################


class Event(object):
	"""Represents an Apple event (serialised message)."""
	
	def __init__(self, address, event, params={}, atts={}, transaction= kae.kAnyTransactionID, 
			returnid= kae.kAutoGenerateReturnID, codecs=_defaultCodecs):
		"""Called by aem.send.__init__.Application.event(); users shouldn't instantiate this class themselves.
			address : AEAddressDesc -- the target application
			event : str -- 8-letter code indicating event's class and id, e.g. 'coregetd'
			params : dict -- a dict of form {AE_code:anything,...} containing zero or more event parameters (message arguments)
			atts : dict -- a dict of form {AE_code:anything,...} containing zero or more event attributes (event info)
			transaction : int -- transaction number (default = kAnyTransactionID)
			returnid : int  -- reply event's ID (default = kAutoGenerateReturnID)
			codecs : Codecs -- user can provide custom parameter & result encoder/decoder (default = standard codecs); supplied by Application class
		"""
		self._eventCode = event
		self._codecs = codecs
		self.AEM_event = self._createAppleEvent(event[:4], event[4:], address, returnid, transaction)
		for key, value in atts.items():
			self.AEM_event.AEPutAttributeDesc(key, codecs.pack(value))
		for key, value in params.items():
			self.AEM_event.AEPutParamDesc(key, codecs.pack(value))
	
	# Hooks
	
	_createAppleEvent = AECreateAppleEvent
	
	def _sendAppleEvent(self, flags, timeout):
		"""Hook method; may be overridden to modify event sending."""
		return self.AEM_event.AESendMessage(flags, timeout)
	
	# Public
	
	def send(self, timeout= kae.kAEDefaultTimeout, flags= kae.kAECanSwitchLayer + kae.kAEWaitReply):
		"""Send this Apple event (may be called any number of times).
			timeout : int | aem.k.DefaultTimeout | aem.k.NoTimeout -- number of ticks to wait for target process to reply before raising timeout error (default=DefaultTimeout)
			flags : int -- bitwise flags [1] indicating how target process should handle event (default=WaitReply)
			Result : anything -- value returned by application, if any
			
			[1] aem.k provides the following constants for convenience:
			
				[ aem.k.NoReply | aem.k.QueueReply | aem.k.WaitReply ]
				[ aem.k.DontReconnect ]
				[ aem.k.WantReceipt ]
				[ aem.k.NeverInteract | aem.k.CanInteract | aem.k.AlwaysInteract ]
				[ aem.k.CanSwitchLayer ]
		"""
		try:
			replyEvent = self._sendAppleEvent(flags, timeout)
		except MacOSError, err: # an OS-level error occurred
			if not (self._eventCode == 'aevtquit' and err[0] == -609): # Ignore invalid connection error (-609) when quitting
				raise CommandError(err[0], '', None)
		else: # decode application's reply, if any
			if replyEvent.type != kae.typeNull:
				eventResult = dict([replyEvent.AEGetNthDesc(i + 1, kae.typeWildCard) 
						for i in range(replyEvent.AECountItems())])
				# note: while Apple docs say that both keyErrorNumber and keyErrorString should be
				# tested for when determining if an error has occurred, AppleScript tests for keyErrorNumber
				# only, so do the same here for compatibility
				if eventResult.has_key(kae.keyErrorNumber): # an application-level error occurred
					# note: uses standard codecs to unpack error info to ensure consistent conversion
					eNum = _defaultCodecs.unpack(eventResult[kae.keyErrorNumber])
					if eNum != 0: # Stupid Finder returns non-error error number and message for successful move/duplicate command, so just ignore it
						eMsg = eventResult.get(kae.keyErrorString)
						if eMsg:
							eMsg = _defaultCodecs.unpack(eMsg)
						raise CommandError(eNum, eMsg, replyEvent)
				if eventResult.has_key(kae.keyAEResult): # application has returned a value
					# note: unpack result with [optionally] user-specified codecs, allowing clients to customise unpacking (e.g. appscript)
					return self._codecs.unpack(eventResult[kae.keyAEResult])



######################################################################


class CommandError(MacOSError):
	"""Represents an error message returned by application/Apple Event Manager.
	
		Attributes:
			number : int -- MacOS error number
			message : str | None -- application error message, if any
			raw : AppleEvent | None -- raw reply event, in case alternate/additional processing of error info is required, or None if error occurred while outgoing event was being sent
	"""
	
	_carbonerrors = { # Following error descriptions are mostly cribbed from AppleScript Language Guide.
		# OS errors
		-34: "Disk is full.",
		-35: "Disk wasn't found.",
		-37: "Bad name for file.",
		-38: "File wasn't open.",
		-39: "End of file error.",
		-42: "Too many files open.",
		-43: "File wasn't found.",
		-44: "Disk is write protected.",
		-45: "File is locked.",
		-46: "Disk is locked.",
		-47: "File is busy.",
		-48: "Duplicate file name.",
		-49: "File is already open.",
		-50: "Parameter error.",
		-51: "File reference number error.",
		-61: "File not open with write permission.",
		-108: "Out of memory.",
		-120: "Folder wasn't found.",
		-124: "Disk is disconnected.",
		-128: "User canceled.",
		-192: "A resource wasn't found.",
		-600: "Application isn't running.",
		-601: "Not enough room to launch application with special requirements.",
		-602: "Application is not 32-bit clean.",
		-605: "More memory is needed than is specified in the size resource.",
		-606: "Application is background-only.",
		-607: "Buffer is too small.",
		-608: "No outstanding high-level event.",
		-609: "Connection is invalid.",
		-904: "Not enough system memory to connect to remote application.",
		-905: "Remote access is not allowed.",
		-906: "Application isn't running or program linking isn't enabled.",
		-915: "Can't find remote machine.",
		-30720: "Invalid date and time.",
		# AE errors
		-1700: "Can't make some data into the expected type.",
		-1701: "Some parameter is missing for command.",
		-1702: "Some data could not be read.",
		-1703: "Some data was the wrong type.",
		-1704: "Some parameter was invalid.",
		-1705: "Operation involving a list item failed.",
		-1706: "Need a newer version of the Apple Event Manager.",
		-1707: "Event isn't an Apple event.",
		-1708: "Application could not handle this command.",
		-1709: "AEResetTimer was passed an invalid reply.",
		-1710: "Invalid sending mode was passed.",
		-1711: "User canceled out of wait loop for reply or receipt.",
		-1712: "Apple event timed out.",
		-1713: "No user interaction allowed.",
		-1714: "Wrong keyword for a special function.",
		-1715: "Some parameter wasn't understood.",
		-1716: "Unknown Apple event address type.",
		-1717: "The handler is not defined.",
		-1718: "Reply has not yet arrived.",
		-1719: "Can't get reference. Invalid index.",
		-1720: "Invalid range.",
		-1721: "Wrong number of parameters for command.",
		-1723: "Can't get reference. Access not allowed.",
		-1725: "Illegal logical operator called.",
		-1726: "Illegal comparison or logical.",
		-1727: "Expected a reference.",
		-1728: "Can't get reference.",
		-1729: "Object counting procedure returned a negative count.",
		-1730: "Container specified was an empty list.",
		-1731: "Unknown object type.",
		-1739: "Attempting to perform an invalid operation on a null descriptor.",
		# Application scripting errors
		-10000: "Apple event handler failed.",
		-10001: "Type error.",
		-10002: "Invalid key form.",
		-10003: "Can't set reference to given value. Access not allowed.",
		-10004: "A privilege violation occurred.",
		-10005: "The read operation wasn't allowed.",
		-10006: "Can't set reference to given value.",
		-10007: "The index of the event is too large to be valid.",
		-10008: "The specified object is a property, not an element.",
		-10009: "Can't supply the requested descriptor type for the data.",
		-10010: "The Apple event handler can't handle objects of this class.",
		-10011: "Couldn't handle this command because it wasn't part of the current transaction.",
		-10012: "The transaction to which this command belonged isn't a valid transaction.",
		-10013: "There is no user selection.",
		-10014: "Handler only handles single objects.",
		-10015: "Can't undo the previous Apple event or user action.",
		-10023: "Enumerated value is not allowed for this property.",
		-10024: "Class can't be an element of container.",
		-10025: "Illegal combination of properties settings.",
	}
	
	# Following Cocoa Scripting error descriptions taken from:
	# http://developer.apple.com/documentation/Cocoa/Reference/Foundation/ObjC_classic/Classes/NSScriptCommand.html
	# http://developer.apple.com/documentation/Cocoa/Reference/Foundation/ObjC_classic/Classes/NSScriptObjectSpecifier.html

	_cocoaerrors = (
		('NSReceiverEvaluationScriptError', 'The object or objects specified by the direct parameter to a command could not be found.'),
		('NSKeySpecifierEvaluationScriptError', 'The object or objects specified by a key (for commands that support key specifiers) could not be found.'),
		('NSArgumentEvaluationScriptError', 'The object specified by an argument could not be found.'),
		('NSReceiversCantHandleCommandScriptError', "The receivers don't support the command sent to them."),
		('NSRequiredArgumentsMissingScriptError', 'An argument (or more than one argument) is missing.'),
		('NSArgumentsWrongScriptError', 'An argument (or more than one argument) is of the wrong type or is otherwise invalid.'),
		('NSUnknownKeyScriptError', 'An unidentified error occurred; indicates an error in the scripting support of your application.'),
		('NSInternalScriptError', 'An unidentified internal error occurred; indicates an error in the scripting support of your application.'),
		('NSOperationNotSupportedForKeyScriptError', 'The implementation of a scripting command signaled an error.'),
		('NSCannotCreateScriptCommandError', 'Could not create the script command; an invalid or unrecognized Apple event was received.'),
		('NSNoSpecifierError', 'No error encountered.'),
		('NSNoTopLevelContainersSpecifierError', 'Someone called evaluate with nil.'),
		('NSContainerSpecifierError', 'Error evaluating container specifier.'),
		('NSUnknownKeySpecifierError', 'Receivers do not understand the key.'),
		('NSInvalidIndexSpecifierError', 'Index out of bounds.'),
		('NSInternalSpecifierError', 'Other internal error.'),
		('NSOperationNotSupportedForKeySpecifierError', 'Attempt made to perform an unsupported operation on some key.'),
	)
	
	def __init__(self, number, message, raw):
		MacOSError.__init__(self, number)
		self.number, self.message, self.raw = number, message, raw
	
	def __repr__(self):
		return "aem.CommandError(%r, %r, %r)" % (self.number, self.message, self.raw)
		
	def __int__(self):
		return self.number
	
	def __str__(self):
		message = self.message
		if self.number > 0:
			for name, description in self._cocoaerrors:
				if message.startswith(name):
					message = '%s (%s)' % (message, description)
					break
		elif not message:
			message = self._carbonerrors.get(self.number, 'OS error')
		return "CommandError: %s (%i)" % (message, self.number)
