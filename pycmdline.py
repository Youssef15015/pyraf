"""pycmdline.py -- Python/CL command line interface for Pyraf

Provides this functionality:

- Command directives:
	.logfile [filename [append]]
	.exit
	.help
	.clemulate
	.debug
- Shell escapes (!cmd, !!cmd to run in /bin/sh)
- CL command-mode execution, triggered by a line that starts with a
  CL task token and is not followed by other characters indicating
  it is some other kind of Python statement
- Normal Python mode execution (when CL emulation and directives are
  not triggered)

Uses standard code module plus some ideas from cmd.py module
(and of course Perry's Monty design.)

$Id$

R. White, 1999 December 14
"""

#XXX additional ideas:
#XXX add command-line completion?

import string, re, os, sys, code, types, keyword
import minmatch
import pyraf, iraf

class CmdConsole(code.InteractiveConsole):
	"""Base class for command console.

	Similar to InteractiveConsole, but provides local prompt control and
	hook for simple non-Python command processing.
	"""

	def __init__(self, locals=None, filename="<console>",
			cmddict=None, prompt1=">>> ", prompt2="... ",
			cmdchars=("a-zA-Z_.","0-9_")):
		code.InteractiveConsole.__init__(self, locals=locals, filename=filename)
		self.ps1 = prompt1
		self.ps2 = prompt2
		if cmddict==None: cmddict={}
		self.cmddict = cmddict
		# cmdchars gives character set for first character, following
		# characters in the command name
		# create pattern that puts command in group 'cmd' and matches
		# optional leading and trailing whitespace
		self.recmd = re.compile( "[ \t]*(?P<cmd>" +
			"[" + cmdchars[0] + "][" + cmdchars[0] + cmdchars[1] + "]*" +
			")[ \t]*")

	def interact(self, banner=None):
		"""Emulate the interactive Python console, with extra commands.
		
		Also is modified so it does not catch EOFErrors."""
		if banner is None:
			self.write("Python %s on %s\n%s\n(%s)\n" %
						(sys.version, sys.platform, sys.copyright,
						self.__class__.__name__))
		else:
			self.write("%s\n" % str(banner))
		more = 0
		# number of consecutive EOFs
		neofs = 0
		while 1:
			try:
				if not sys.stdin.isatty():
					prompt = ""
				elif more:
					prompt = self.ps2
				else:
					prompt = self.ps1
				line = self.raw_input(prompt)
				neofs = 0
				# note that this forbids combination of python & CL
				# code -- e.g. a for loop that runs CL tasks.
				if not more:
					line = self.cmd(line)
				if line or more: more = self.push(line)
			except EOFError:
				#XXX ugly code here -- refers to methods
				#XXX defined in extensions of this class
				neofs = neofs+1
				if neofs>=5:
					self.write("\nToo many EOFs, exiting now\n")
					self.do_exit('',0)
				self.write("\nUse .exit to exit\n"
					".help describes executive commands\n")
				self.resetbuffer()
				more = 0
			except KeyboardInterrupt:
				self.write("\nKeyboardInterrupt\n")
				self.resetbuffer()
				more = 0

	def cmd(self, line):
		"""Check for and execute commands from dictionary."""
		mo = self.recmd.match(line)
		if mo is None:
			i = 0
			cmd = ''
			method_name = None
		else:
			cmd = mo.group('cmd')
			i = mo.end()
			# look up command in dictionary
			try:
				method_name = self.cmddict[cmd]
			except KeyError:
				method_name = None
		if method_name is None:
			# no method, but have a look at it anyway
			return self.default(cmd,line,i)
		else:
			# if in cmddict, there must be a method by this name
			f = getattr(self, method_name)
			return apply(f, (line, i))

	def default(self, cmd, line, i):
		"""Hook to handle other commands (this version does nothing)"""
		return line

# put the executive commands in a minimum match dictionary

_cmdDict = minmatch.MinMatchDict({
				'.help': 'do_help',
				'.clemulate': 'do_clemulate',
				'.logfile': 'do_logfile',
				'.exit': 'do_exit',
				'.debug': 'do_debug',
				})

# short CL commands to allow
# there are others that I could add, but are they really necessary?
# bc, cv, dq, fc, nm, od, rc, rv, sh, su, w

_shortCmdDict = {
	'cd': 1,
	'cl': 1,
	'cp': 1,
	'df': 1,
	'du': 1,
	'ls': 1,
	'mv': 1,
	'ps': 1,
	'tv': 1,
	'vi': 1,
	'wc': 1,
	'xc': 1,
	}

class PyCmdLine(CmdConsole):

	"""Simple Python interpreter with executive commands"""

	def __init__(self, locals=None, logfile=None, debug=0, clemulate=1):
		CmdConsole.__init__(self, locals=locals,
			cmddict=_cmdDict, prompt1="--> ", prompt2="... ")
		self.debug = debug
		self.clemulate = clemulate
		self.logfile = None
		if logfile is not None:
			if hasattr(logfile,'write'):
				self.logfile = logfile
			elif type(logfile) is types.StringType:
				self.do_logfile(logfile, 0)
			else:
				self.write('logfile ignored -- not string or filehandle\n')

	def runsource(self, source, filename="<input>", symbol="single"):
		"""Compile and run some source in the interpreter.

		Modified from code.py to include logging."""
		try:
			pcode = code.compile_command(source, filename, symbol)
		except (OverflowError, SyntaxError):
			# Case 1
			self.showsyntaxerror(filename)
			return 0

		if pcode is None:
			# Case 2
			return 1

		# Case 3
		self.runcode(pcode)
		if self.logfile:
			self.logfile.write(source)
			if source[-1:] != '\n': self.logfile.write('\n')
			self.logfile.flush()
		return 0

	def do_help(self, line, i):
		"""Print help on executive commands"""
		if self.debug: self.write('do_help: %s\n' % line[i:])
		self.write("""Executive commands:
.logfile [filename [append|overwrite]]
    If filename is specified, start logging commands to the file.  If filename
    is omitted, turns off logging.  The optional append/overwrite argument
    determines whether output is appended to (default) or overwrites an
    existing file.
.clemulate [0|1]
    Set the CL emulation flag, which determines whether lines starting
    with a CL task name are interpreted in CL mode rather than Python mode.
    If argument is omitted, default is 1 (turn on CL emulation.)
.exit
    Exit from Pyraf.
.help
    Print this help message.
.debug [1|0]
    Set the debugging flag.  If argument is omitted, default value is 1
    (turn on debugging.)

Commands can be abbreviated.
""")

	def do_exit(self, line, i):
		"""Exit from Python"""
		if self.debug: self.write('do_exit: %s\n' % line[i:])
		raise SystemExit

	def do_logfile(self, line, i):
		"""Start or stop logging commands"""
		if self.debug: self.write('do_logfile: %s\n' % line[i:])
		args = string.split(line[i:])
		if len(args) == 0:	# turn off logging (if on)
			if self.logfile:
				self.logfile.close()
				self.logfile = None
			else:
				self.write("No log file currently open\n")
		else:
			filename = args[0]
			del args[0]
			oflag = 'a'
			if len(args) > 0:
				sarg = string.strip(args[0])
				if args[0] == 'overwrite':
					oflag = 'w'
					del args[0]
				elif args[0] == 'append':
					del args[0]
			if args:
				self.write('Ignoring unknown options: %s\n' %
					string.join(args," "))
			try:
				oldlogfile = self.logfile
				self.logfile = open(filename,oflag)
				if oldlogfile: oldlogfile.close()
			except IOError, e:
				self.write("error opening logfile %s\n%s\n" % (filename,str(e)))
		return ""

	def do_clemulate(self, line, i):
		"""Turn CL emulation on or off"""
		if self.debug: self.write('do_clemulate: %s\n' % line[i:])
		self.clemulate = 1
		if line[i:] != "":
			try:
				self.clemulate = int(line[i:])
			except ValueError, e:
				if self.debug: self.write(str(e)+'\n')
				pass
		return ""

	def do_debug(self, line, i):
		"""Turn debug output on or off"""
		if self.debug: self.write('do_debug: %s\n' % line[i:])
		self.debug = 1
		if line[i:] != "":
			try:
				self.debug = int(line[i:])
			except ValueError, e:
				if self.debug: self.write(str(e)+'\n')
				pass
		return ""


	def default(self, cmd, line, i):
		"""Check for IRAF task calls and use CL emulation mode if needed

		cmd = alpha-numeric string from beginning of line
		line = full line (including cmd, preceding blanks, etc.)
		i = index in line of first non-blank character following cmd
		"""
		if self.debug: self.write('default: %s - %s\n' % (cmd,line[i:]))
		if len(cmd)==0:
			if line[i:i+1] == '!':
				# '!' is shell escape
				# handle it here only if cl emulation is turned off
				if not self.clemulate:
					iraf.clOscmd(line[i+1:])
					return ''
			elif line[i:i+1] != '?':
				# leading '?' will be handled by CL code -- else this is Python
				return line
		elif self.clemulate == 0:
			# if CL emulation is turned off then just return
			return line
		elif keyword.iskeyword(cmd) or \
		  (os.__builtins__.has_key(cmd) and cmd != 'dir'):
			# don't mess with Python keywords or built-in functions
			# except allow 'dir' to be used for directory listings
			return line
		elif line[i:i+1] != "" and line[i] in '=,[':
			# don't even try if it doesn't look like a procedure call
			return line
		else:
			# see if cmd is an IRAF task or procedure name
			try:
				t = getattr(iraf,cmd)
				# OK, we found it in the iraf module
				# If it could be a Python expression, check to see
				# if the function exists in the local namespace
				if line[i:i+1] == '(':
					if self.isLocal(cmd) or cmd == 'dir': return line
					# Not a local function, so user presumably intends to
					# call IRAF task.  Force Python mode but add the 'iraf.'
					# string to the task name for convenience.
					j = string.find(line,cmd)
					return line[:j] + 'iraf.' + line[j:]
				elif self.isLocal(cmd) and line[i:i+1] != "" and \
				  line[i] not in string.digits and \
				  line[i] not in string.letters and \
				  line[i] not in "<>|":
					# don't override local variable unless this really
					# does not look like a legal Python command
					return line
			except AttributeError, e:
				return line

		# if we get to here then it looks like CL code
		if self.debug: self.write('CL: %s\n' % line)
		try:
			code = iraf.clExecute(line, locals=self.locals, mode='single')
			if self.logfile is not None:
				# log CL code as comment
				cllines = string.split(line,'\n')
				for oneline in cllines:
					self.logfile.write('# %s\n' % oneline)
				self.logfile.write(code)
				self.logfile.flush()
		except:
			self.showtraceback()
		return ''

	def isLocal(self, value):
		"""Returns true if value is local variable"""
		ff = string.split(value,'.')
		if self.locals.has_key(ff[0]):
			return 1
		else:
			return 0

	def start(self, banner="Python/CL command line wrapper\n"
			"  .help describes executive commands"):
		"""Start interpreter"""
		self.interact(banner=banner)
