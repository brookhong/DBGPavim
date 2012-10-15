# vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab
# -*- c--oding: ko_KR.UTF-8 -*-
# remote PHP debugger : remote debugger interface to DBGp protocol
#
# Copyright (c) 2012 Brook Hong
#
# The MIT License
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify,
# merge, publish, distribute, sublicense, and/or sell copies of the
# Software, and to permit persons to whom the Software is furnished
# to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included
# in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
# OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
# CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
# TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
# SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#
#
# Authors:
#    Brook Hong <hzgmaxwell <at> hotmail.com>
#    The plugin was originally writen by --
#    Seung Woo Shin <segv <at> sayclub.com>
#    I rewrote it with a new debugger engine, please diff this file to find code change.

import os
import sys
import vim
import socket
import base64
import traceback
import xml.dom.minidom

import string
import time, subprocess
from threading import Thread,Lock

def getFilePath(s):
  fn = s[7:]
  win = 0
  if fn[2] == ':':
    fn = fn[1:]
    win = 1
  return [fn, win]
class VimWindow:
  """ wrapper class of window of vim """
  def __init__(self, name = 'DEBUG_WINDOW'):
    """ initialize """
    self.name       = name
    self.method     = "new"
    self.buffer     = None
    self.firstwrite = 1
  def isprepared(self):
    """ check window is OK """
    if self.buffer == None or len(dir(self.buffer)) == 0 or self.getwinnr() == -1:
      return 0
    return 1
  def prepare(self):
    """ check window is OK, if not then create """
    if not self.isprepared():
      self.create(self.method)
  def before_create(self):
    vim.command("1wincmd w")
  def on_create(self):
    pass
  def getwinnr(self):
    return int(vim.eval("bufwinnr('"+self.name+"')"))
  def focus(self):
    winnr = self.getwinnr()
    vim.command(str(winnr) + 'wincmd w')
  def getWidth(self):
    return int(vim.eval("winwidth(bufwinnr('"+self.name+"'))"))
  def getHeight(self):
    return int(vim.eval("winheight(bufwinnr('"+self.name+"'))"))
  def xml_on_element(self, node):
    line = str(node.nodeName)
    if node.hasAttributes():
      for (n,v) in node.attributes.items():
        line += str(' %s=%s' % (n,v))
    return line
  def xml_on_attribute(self, node):
    return str(node.nodeName)
  def xml_on_entity(self, node):
    return 'entity node'
  def xml_on_comment(self, node):
    return 'comment node'
  def xml_on_document(self, node):
    return '#document'
  def xml_on_document_type(self, node):
    return 'document type node'
  def xml_on_notation(self, node):
    return 'notation node'
  def xml_on_text(self, node):
    return node.data
  def xml_on_processing_instruction(self, node):
    return 'processing instruction'
  def xml_on_cdata_section(self, node):
    return node.data

  def write(self, msg):
    """ append last """
    self.prepare()
    if self.firstwrite == 1:
      self.firstwrite = 0
      self.buffer[:] = str(msg).split('\n')
    else:
      self.buffer.append(str(msg).split('\n'))
    self.command('normal G')
    #self.window.cursor = (len(self.buffer), 1)
  def create(self, method = 'new'):
    """ create window """
    self.method = method
    self.before_create()
    vim.command('silent ' + method + ' ' + self.name)
    #if self.name != 'LOG___WINDOW':
    vim.command("setlocal buftype=nofile")
    self.buffer = vim.current.buffer
    self.width  = int( vim.eval("winwidth(0)")  )
    self.height = int( vim.eval("winheight(0)") )
    self.on_create()
  def destroy(self):
    """ destroy window """
    if self.buffer == None or len(dir(self.buffer)) == 0:
      return
    #if self.name == 'LOG___WINDOW':
    #  self.command('hide')
    #else:
    self.command('bdelete ' + self.name)
    self.firstwrite = 1
  def clean(self):
    """ clean all datas in buffer """
    self.prepare()
    self.buffer[:] = []
    self.firstwrite = 1
  def command(self, cmd):
    """ go to my window & execute command """
    self.prepare()
    winnr = self.getwinnr()
    if winnr != int(vim.eval("winnr()")):
      vim.command(str(winnr) + 'wincmd w')
    vim.command(cmd)

  def _xml_stringfy(self, node, level = 0, encoding = None):
    if node.nodeType   == node.ELEMENT_NODE:
      line = self.xml_on_element(node)

    elif node.nodeType == node.ATTRIBUTE_NODE:
      line = self.xml_on_attribute(node)

    elif node.nodeType == node.ENTITY_NODE:
      line = self.xml_on_entity(node)

    elif node.nodeType == node.COMMENT_NODE:
      line = self.xml_on_comment(node)

    elif node.nodeType == node.DOCUMENT_NODE:
      line = self.xml_on_document(node)

    elif node.nodeType == node.DOCUMENT_TYPE_NODE:
      line = self.xml_on_document_type(node)

    elif node.nodeType == node.NOTATION_NODE:
      line = self.xml_on_notation(node)

    elif node.nodeType == node.PROCESSING_INSTRUCTION_NODE:
      line = self.xml_on_processing_instruction(node)

    elif node.nodeType == node.CDATA_SECTION_NODE:
      line = self.xml_on_cdata_section(node)

    elif node.nodeType == node.TEXT_NODE:
      line = self.xml_on_text(node)

    else:
      line = 'unknown node type'

    if node.hasChildNodes():
      #print ''.ljust(level*4) + '{{{' + str(level+1)
      #print ''.ljust(level*4) + line
      return self.fixup_childs(line, node, level)
    else:
      return self.fixup_single(line, node, level)

    return line

  def fixup_childs(self, line, node, level):
    line = ''.ljust(level*4) + line +  '\n'
    line += self.xml_stringfy_childs(node, level+1)
    return line
  def fixup_single(self, line, node, level):
    return ''.ljust(level*4) + line + '\n'

  def xml_stringfy(self, xml):
    return self._xml_stringfy(xml)
  def xml_stringfy_childs(self, node, level = 0):
    line = ''
    for cnode in node.childNodes:
      line = str(line)
      line += str(self._xml_stringfy(cnode, level))
    return line

  def write_xml(self, xml):
    self.write(self.xml_stringfy(xml))
  def write_xml_childs(self, xml):
    self.write(self.xml_stringfy_childs(xml))

class StackWindow(VimWindow):
  def __init__(self, name = 'STACK_WINDOW'):
    VimWindow.__init__(self, name)
  def xml_on_element(self, node):
    if node.nodeName != 'stack':
      return VimWindow.xml_on_element(self, node)
    else:
      if node.getAttribute('where') != '{main}':
        fmark = '()'
      else:
        fmark = ''
      [fn, win] = getFilePath(node.getAttribute('filename'))
      fn = dbgPavim.localPathOf(fn)
      return str('%-2s %-15s %s:%s' % (      \
          node.getAttribute('level'),        \
          node.getAttribute('where')+fmark,  \
          fn, \
          node.getAttribute('lineno')))
  def on_create(self):
    self.command('highlight CurStack term=reverse ctermfg=White ctermbg=Red gui=reverse')
    self.highlight_stack(0)
  def highlight_stack(self, no):
    self.command('syntax clear')
    self.command('syntax region CurStack start="^' +str(no)+ ' " end="$"')

class TraceWindow(VimWindow):
  def __init__(self, name = 'TRACE_WINDOW'):
    VimWindow.__init__(self, name)
  def xml_on_element(self, node):
    if node.nodeName != 'error':
      return VimWindow.xml_on_element(self, node)
    else:
      desc = ''
      if node.hasAttribute('code'):
        desc = ' : '+error_msg[int(node.getAttribute('code'))]
      return VimWindow.xml_on_element(self, node) + desc
  def on_create(self):
    self.command('set wrap fdm=marker fmr={{{,}}} fdl=0')

class WatchWindow(VimWindow):
  def __init__(self, name = 'WATCH_WINDOW'):
    VimWindow.__init__(self, name)
  def fixup_single(self, line, node, level):
    return ''.ljust(level*1) + line + '\n'
  def fixup_childs(self, line, node, level):
    if len(node.childNodes)      == 1              and \
       (node.firstChild.nodeType == node.TEXT_NODE  or \
       node.firstChild.nodeType  == node.CDATA_SECTION_NODE):
      line = str(''.ljust(level*1) + line)
      encoding = node.getAttribute('encoding')
      if encoding == 'base64':
        line += "'" + base64.decodestring(str(node.firstChild.data)) + "';\n"
      elif encoding == '':
        line += str(node.firstChild.data) + ';\n'
      else:
        line += '(e:'+encoding+') ' + str(node.firstChild.data) + ';\n'
    else:
      if level == 0:
        line = ''.ljust(level*1) + str(line) + '\n'
        line += self.xml_stringfy_childs(node, level+1)
        line += '\n'
      else:
        line = (''.ljust(level*1) + str(line) + ';') + '\n'
        line += str(self.xml_stringfy_childs(node, level+1))
    return line
  def xml_on_element(self, node):
    if node.nodeName == 'property':
      self.type = node.getAttribute('type')

      name      = node.getAttribute('name')
      fullname  = node.getAttribute('fullname')
      if name == '':
        name = 'EVAL_RESULT'
      if fullname == '':
        fullname = 'EVAL_RESULT'

      if self.type == 'uninitialized':
        return str(('%-20s' % name) + " = /* uninitialized */'';")
      else:
        return str('%-20s' % fullname) + ' = (' + self.type + ') '
    elif node.nodeName == 'response':
      return '// by ' + node.getAttribute('command')
    else:
      return VimWindow.xml_on_element(self, node)

  def xml_on_text(self, node):
    if self.type == 'string':
      return "'" + str(node.data) + "'"
    else:
      return str(node.data)
  def xml_on_cdata_section(self, node):
    if self.type == 'string':
      return "'" + str(node.data) + "'"
    else:
      return str(node.data)
  def on_create(self):
    self.write('<?')
    self.command('inoremap <buffer> <cr> <esc>:python dbgPavim.debugSession.watch_execute()<cr>')
    self.command('set noai nocin')
    self.command('set wrap fdm=manual fmr={{{,}}} ft=php fdl=1')
  def input(self, mode, arg = ''):
    self.prepare()
    line = self.buffer[-1]
    if line[:len(mode)+1] == '// => '+mode+':':
      self.buffer[-1] = line + arg
    else:
      self.buffer.append('// => '+mode+': '+arg)
    self.command('normal G')
  def get_command(self):
    line = self.buffer[-1]
    if line[0:11] == '// => exec:':
      print "exec does not supported by xdebug now."
      return ('none', '')
      #return ('exec', line[11:].strip(' '))
    elif line[0:11] == '// => eval:':
      return ('eval', line[11:].strip(' '))
    elif line[0:19] == '// => property_get:':
      return ('property_get', line[19:].strip(' '))
    elif line[0:18] == '// => context_get:':
      return ('context_get', line[18:].strip(' '))
    else:
      return ('none', '')

class HelpWindow(VimWindow):
  def __init__(self, name = 'HELP__WINDOW'):
    VimWindow.__init__(self, name)
  def before_create(self):
    pass
  def on_create(self):
    self.write(                                                          \
        '[ Function Keys ]                    | [ Command Mode ]             \n' + \
        '  <F1>   toggle help window          | :Bp toggle breakpoint        \n' + \
        '  <F2>   step into                   | :Up stack up                 \n' + \
        '  <F3>   step over                   | :Dn stack down               \n' + \
        '  <F4>   step out                    | :Bl list breakpoints         \n' + \
        '  <F5>   run                         | :Pg property get             \n' + \
        '  <F6>   quit debugging              | <F9>   toggle layout         \n' + \
        '  <F7>   eval                        | <F11>  get all context       \n' + \
        '  <F8>   toggle dbgPavimBreakAtEntry | <F12>  get property at cursor\n' + \
        '                                                                    \n' + \
        '  For more instructions and latest version,                         \n' + \
        '               pleae refer to https://github.com/brookhong/DBGPavim \n' + \
        '')
    self.command('1')

class ConsoleWindow(VimWindow):
  def __init__(self, name = 'CONSOLE__WINDOW'):
    VimWindow.__init__(self, name)
  def before_create(self):
    pass
  def on_create(self):
    vim.command('setlocal autoread')

class DebugUI:
  """ DEBUGUI class """
  (NORMAL, DEBUG) = (0,1)
  def __init__(self, stackwinHeight, watchwinWidth):
    """ initialize object """
    self.watchwin       = WatchWindow()
    self.stackwin       = StackWindow()
    self.stackwinHeight = stackwinHeight
    self.watchwinWidth  = watchwinWidth
    self.tracewin       = None
    self.helpwin        = None
    self.mode           = DebugUI.NORMAL
    self.file           = None
    self.line           = None
    self.winbuf         = {}
    self.cursign        = None
    self.sessfile       = os.getenv("HOME").replace("\\","/")+"/dbgpavim_saved_session." + str(os.getpid())
    self.clilog         = os.getenv("HOME").replace("\\","/")+"/dbgpavim_cli." + str(os.getpid())
    self.cliwin         = None
    self.backup_ssop    = vim.eval('&ssop')

  def trace(self):
    if self.tracewin:
      self.tracewin.destroy()
      self.tracewin = None
    else:
      self.tracewin = TraceWindow()
      self.tracewin.create('belowright new')

  def debug_mode(self):
    """ change mode to debug """
    if self.mode == DebugUI.DEBUG:
      return
    self.mode = DebugUI.DEBUG
    # save session
    vim.command('set ssop-=tabpages')
    vim.command('mksession! ' + self.sessfile)
    for i in range(1, len(vim.windows)+1):
      vim.command(str(i)+'wincmd w')
      self.winbuf[i] = vim.eval('bufnr("%")') # save buffer number, mksession does not do job perfectly
                                              # when buffer is not saved at all.

    vim.command('silent topleft new')                # create srcview window (winnr=1)
    for i in range(2, len(vim.windows)+1):
      vim.command(str(i)+'wincmd w')
      vim.command('hide')
    self.create()
    vim.command('1wincmd w') # goto srcview window(nr=1, top-left)
    self.cursign = '1'

    self.set_highlight()

    vim.command('call CreateFunctionKeys()')
  def normal_mode(self):
    """ restore mode to normal """
    if self.mode == DebugUI.NORMAL:
      return

    vim.command('call ClearFunctionKeys()')
    vim.command('sign unplace 1')
    vim.command('sign unplace 2')

    # destory all created windows
    self.destroy()

    # restore session
    vim.command('source ' + self.sessfile)
    vim.command("let &ssop=\""+self.backup_ssop+"\"")
    os.remove(self.sessfile)

    self.set_highlight()

    self.winbuf.clear()
    self.file    = None
    self.line    = None
    self.mode    = DebugUI.NORMAL
    self.cursign = None
    self.cliwin  = None
  def create(self):
    """ create windows """
    self.stackwin.create('botright '+str(self.stackwinHeight)+' new')
    if self.cliwin:
      self.cliwin.create('vertical new')
    self.watchwin.create('vertical belowright '+str(self.watchwinWidth)+' new')
  def reLayout(self):
    if self.stackwin.getHeight() != self.stackwinHeight or self.watchwin.getWidth() != self.watchwinWidth:
      self.stackwin.command("resize "+str(self.stackwinHeight))
      self.watchwin.command("vertical resize "+str(self.watchwinWidth))
    else:
      vim.command("wincmd _")
      vim.command("wincmd |")

  def set_highlight(self):
    """ set vim highlight of debugger sign """
    vim.command("highlight DbgCurrent term=reverse ctermfg=White ctermbg=Red gui=reverse")
    vim.command("highlight DbgBreakPt term=reverse ctermfg=White ctermbg=Green gui=reverse")

  def help(self):
    if self.helpwin:
      self.helpwin.destroy()
      self.helpwin = None
    else:
      self.helpwin  = HelpWindow('HELP__WINDOW')
      self.stackwin.focus()
      self.helpwin.create('vertical new')

  def update_cli(self):
    self.cliwin.focus()
    vim.command('e')
    vim.command('normal G')

  def destroy(self):
    """ destroy windows """
    self.watchwin.destroy()
    self.stackwin.destroy()
    if self.tracewin:
      self.tracewin.destroy()
    if self.cliwin:
      self.cliwin.destroy()
  def go_srcview(self):
    vim.command('1wincmd w')
  def next_sign(self):
    if self.cursign == '1':
      return '2'
    else:
      return '1'
  def set_srcview(self, file, line):
    """ set srcview windows to file:line and replace current sign """

    if file == self.file and self.line == line:
      return

    if file != self.file:
      self.file = file
      self.go_srcview()
      vim.command('silent edit ' + file)

    if self.mode == DebugUI.DEBUG:
      if line == 0:
        line = 1
      nextsign = self.next_sign()
      vim.command('sign place ' + nextsign + ' name=current line='+str(line)+' file='+file)
      vim.command('sign unplace ' + self.cursign)
      vim.command('sign jump ' + nextsign + ' file='+file)
      self.cursign = nextsign
      if self.cliwin:
        self.update_cli()
    else:
      vim.command(': ' + str(line))

    self.line    = line

class DbgSession:
  def __init__(self, sock):
    self.latestRes = None
    self.msgid = 0
    self.sock = sock
    self.isWinServer = 0
    self.bptsetlst  = {}
    self.bptsetids  = {}
  def jump(self, fn, line):
    vim.command("e +"+str(line)+" "+str(fn))
  def handle_response_breakpoint_set(self, res):
    """handle <response command=breakpoint_set> tag
    <responsponse command="breakpoint_set" id="110180001" transaction_id="1"/>"""
    if res.firstChild.hasAttribute('id'):
      tid = int(res.firstChild.getAttribute('transaction_id'))
      bno = self.bptsetlst[tid]
      del self.bptsetlst[tid]
      self.bptsetids[bno] = res.firstChild.getAttribute('id')
  def getbid(self, bno):
    """ get Debug Server's breakpoint numbered with bno """
    if bno in self.bptsetids:
      return self.bptsetids[bno]
    return None
  def recv_data(self,len):
    c = self.sock.recv(len)
    if c == '':
      # LINUX come here
      raise EOFError, 'Socket Closed'
    return c
  def recv_length(self):
    #print '* recv len'
    length = ''
    while 1:
      c = self.recv_data(1)
      #print '  GET(',c, ':', ord(c), ') : length=', len(c)
      if c == '\0':
        return int(length)
      if c.isdigit():
        length = length + c
  def recv_null(self):
    while 1:
      c = self.recv_data(1)
      if c == '\0':
        return
  def recv_body(self, to_recv):
    body = ''
    while to_recv > 0:
      buf = self.recv_data(to_recv)
      to_recv -= len(buf)
      body = body + buf
    return body
  def recv_msg(self):
    length = self.recv_length()
    body   = self.recv_body(length)
    self.recv_null()
    return body
  def send_msg(self, cmd):
    self.sock.send(cmd + '\0')
  def handle_recvd_msg(self, res):
    resDom = xml.dom.minidom.parseString(res)
    if resDom.firstChild.tagName == "response":
      if resDom.firstChild.getAttribute('command') == "breakpoint_set":
        self.handle_response_breakpoint_set(resDom)
      if resDom.firstChild.getAttribute('command') == "stop":
        self.close()
    elif resDom.firstChild.tagName == "init":
      [fn, self.isWinServer] = getFilePath(resDom.firstChild.getAttribute('fileuri'))
    return resDom
  def send_command(self, cmd, arg1 = '', arg2 = ''):
    self.msgid = self.msgid + 1
    line = cmd + ' -i ' + str(self.msgid)
    if arg1 != '':
      line = line + ' ' + arg1
    if arg2 != '':
      line = line + ' -- ' + base64.encodestring(arg2)[0:-1]
    self.send_msg(line)
    return self.msgid
  def ack_command(self, count=10000):
    while count>0:
      count = count - 1
      self.latestRes = self.recv_msg()
      resDom = self.handle_recvd_msg(self.latestRes)
      try:
        if int(resDom.firstChild.getAttribute('transaction_id')) == int(self.msgid):
          return resDom
      except:
        pass
  def command(self, cmd, arg1 = '', arg2 = ''):
    self.send_command(cmd, arg1, arg2)
    return self.ack_command()
  def close(self):
    if self.sock:
      self.sock.close()
      self.sock = None
  def init(self):
    if self.latestRes != None:
      return
    self.ack_command(1)
    flag = 0
    for bno in dbgPavim.breakpt.list():
      fn = dbgPavim.remotePathOf(dbgPavim.breakpt.getfile(bno))
      if self.isWinServer:
        fn = fn.replace("/","\\")
      msgid = self.send_command('breakpoint_set', \
                                '-t line -f ' + fn + ' -n ' + str(dbgPavim.breakpt.getline(bno)) + ' -s enabled', \
                                dbgPavim.breakpt.getexp(bno))
      self.bptsetlst[msgid] = bno
      flag = 1
    if flag:
      self.ack_command()

class DbgSessionWithUI(DbgSession):
  def __init__(self, sock):
    self.status     = None
    self.ui         = dbgPavim.ui

    self.msgid      = 0
    self.stacks     = []
    self.curstack   = 0
    self.laststack  = 0
    DbgSession.__init__(self,sock)
  def copyFromParent(self, ss):
    self.latestRes = ss.latestRes
    self.msgid = ss.msgid
    self.isWinServer = ss.isWinServer
    self.sock = ss.sock
    self.bptsetlst  = ss.bptsetlst
    self.bptsetids  = ss.bptsetids
  def init(self):
    self.command('feature_set', '-n max_children -v ' + dbgPavim.max_children)
    self.command('feature_set', '-n max_data -v ' + dbgPavim.max_data)
    self.command('feature_set', '-n max_depth -v ' + dbgPavim.max_depth)
  def start(self):
    self.sock.settimeout(30)
    dbgPavim.updateStatusLine()
    self.ui.debug_mode()

    if self.latestRes != None:
      self.handle_recvd_msg(self.latestRes)
      self.init()
      self.command('stack_get')
    else:
      DbgSession.init(self)
      self.init()
      self.command('step_into')
    self.command('property_get', "-d %d -n $_SERVER['REQUEST_URI']" % (self.laststack))
    self.ui.go_srcview()
  def send_msg(self, cmd):
    """ send message """
    self.sock.send(cmd + '\0')
    # log message
    if self.ui.tracewin:
      self.ui.tracewin.write(str(self.msgid) + ' : send =====> ' + cmd)
  def handle_recvd_msg(self, txt):
    # log messages {{{
    if self.ui.tracewin:
      self.ui.tracewin.write( str(self.msgid) + ' : recv <===== {{{   ' + txt)
      self.ui.tracewin.write('}}}')
    res = xml.dom.minidom.parseString(txt)
    """ call appropraite message handler member function, handle_XXX() """
    fc = res.firstChild
    try:
      handler = getattr(self, 'handle_' + fc.tagName)
      handler(res)
    except AttributeError:
      print 'DBGPavim.handle_'+fc.tagName+'() not found, please see the LOG___WINDOW'
    self.ui.go_srcview()
    return res
  def handle_response(self, res):
    """ call appropraite response message handler member function, handle_response_XXX() """
    if res.firstChild.hasAttribute('reason') and res.firstChild.getAttribute('reason') == 'error':
      self.handle_response_error(res)
      return
    errors  = res.getElementsByTagName('error')
    if len(errors)>0:
      self.handle_response_error(res)
      return

    command = res.firstChild.getAttribute('command')
    try:
      handler = getattr(self, 'handle_response_' + command)
    except AttributeError:
      print 'DBGPavim.handle_response_'+command+'() not found, please see the LOG___WINDOW'
      return
    handler(res)
    return
  def handle_response_stop(self, res):
    dbgPavim.handle_exception()

  def handle_init(self, res):
    """handle <init> tag
    <init appid="7035" fileuri="file:///home/segv/htdocs/index.php" language="PHP" protocol_version="1.0">
      <engine version="2.0.0beta1">
        Xdebug
      </engine>
      <author>
        Derick Rethans
      </author>
      <url>
        http://xdebug.org
      </url>
      <copyright>
        Copyright (c) 2002-2004 by Derick Rethans
      </copyright>
    </init>"""

    [fn, self.isWinServer] = getFilePath(res.firstChild.getAttribute('fileuri'))
    fn = dbgPavim.localPathOf(fn)
    self.ui.set_srcview(fn, 1)

  def handle_response_error(self, res):
    """ handle <error> tag """
    if self.ui.tracewin:
      self.ui.tracewin.write_xml_childs(res)
    errors  = res.getElementsByTagName('error')
    for error in errors:
      code = int(error.getAttribute('code'))
      if code == 5:
        self.command('run')
        break

  def handle_response_stack_get(self, res):
    """handle <response command=stack_get> tag
    <response command="stack_get" transaction_id="1 ">
      <stack filename="file:///home/segv/htdocs/index.php" level="0" lineno="41" where="{main}"/>
    </response>

    for windows
    <response xmlns="urn:debugger_protocol_v1" xmlns:xdebug="http://xdebug.org/dbgp/xdebug" command="stack_get" transaction_id="12">
      <stack where="{main}" level="0" type="file" filename="file:///D:/works/scriptbundle/php/playpen.php" lineno="16">
      </stack>
    </response>
    """

    stacks = res.getElementsByTagName('stack')
    if len(stacks)>0:
      self.curstack  = 0
      self.laststack = len(stacks) - 1

      self.stacks    = []
      for s in stacks:
        [fn, win] = getFilePath(s.getAttribute('filename'))
        fn = dbgPavim.localPathOf(fn)
        self.stacks.append( {'file':  fn, \
                             'line':  int(s.getAttribute('lineno')),  \
                             'where': s.getAttribute('where'),        \
                             'level': int(s.getAttribute('level'))
                             } )

      self.ui.stackwin.clean()
      self.ui.stackwin.highlight_stack(self.curstack)

      self.ui.stackwin.write_xml_childs(res.firstChild) #str(res.toprettyxml()))
      self.ui.set_srcview( self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'] )


  def handle_response_step_out(self, res):
    """handle <response command=step_out> tag
    <response command="step_out" reason="ok" status="break" transaction_id="1 "/>"""
    if res.firstChild.hasAttribute('reason') and res.firstChild.getAttribute('reason') == 'ok':
      if res.firstChild.hasAttribute('status'):
        self.status = res.firstChild.getAttribute('status')
      return
    else:
      print res.toprettyxml()
  def handle_response_step_over(self, res):
    """handle <response command=step_over> tag
    <response command="step_over" reason="ok" status="break" transaction_id="1 "/>"""
    if res.firstChild.hasAttribute('reason') and res.firstChild.getAttribute('reason') == 'ok':
      if res.firstChild.hasAttribute('status'):
        self.status = res.firstChild.getAttribute('status')
      return
    else:
      print res.toprettyxml()
  def handle_response_step_into(self, res):
    """handle <response command=step_into> tag
    <response command="step_into" reason="ok" status="break" transaction_id="1 "/>"""
    if res.firstChild.hasAttribute('reason') and res.firstChild.getAttribute('reason') == 'ok':
      if res.firstChild.hasAttribute('status'):
        self.status = res.firstChild.getAttribute('status')
      return
    else:
      print res.toprettyxml()
  def handle_response_run(self, res):
    """handle <response command=run> tag
    <response command="step_over" reason="ok" status="break" transaction_id="1 "/>"""
    if res.firstChild.hasAttribute('status'):
      self.status = res.firstChild.getAttribute('status')
      return
  def handle_response_eval(self, res):
    """handle <response command=eval> tag """
    self.ui.watchwin.write_xml_childs(res)
  def handle_response_property_get(self, res):
    """handle <response command=property_get> tag """
    self.ui.watchwin.write_xml_childs(res)
  def handle_response_context_get(self, res):
    """handle <response command=context_get> tag """
    self.ui.watchwin.write_xml_childs(res)
  def handle_response_feature_set(self, res):
    """handle <response command=feature_set> tag """
    #self.ui.watchwin.write_xml_childs(res)
  def handle_response_default(self, res):
    """handle <response command=context_get> tag """
    print res.toprettyxml()

  def go(self, stack):
    if stack >= 0 and stack <= self.laststack:
      self.curstack = stack
      self.ui.stackwin.highlight_stack(self.curstack)
      self.ui.set_srcview(self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'])

  def jump(self, fn, line):
    self.ui.set_srcview(fn, line)

  def up(self):
    if self.curstack > 0:
      self.curstack -= 1
      self.ui.stackwin.highlight_stack(self.curstack)
      self.ui.set_srcview(self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'])

  def down(self):
    if self.curstack < self.laststack:
      self.curstack += 1
      self.ui.stackwin.highlight_stack(self.curstack)
      self.ui.set_srcview(self.stacks[self.curstack]['file'], self.stacks[self.curstack]['line'])

  def watch_input(self, mode, arg = ''):
    self.ui.watchwin.input(mode, arg)

  def property_get(self, name = ''):
    if name == '':
      name = vim.eval('expand("<cword>")')
    self.ui.watchwin.write('// property_get: '+name)
    self.command('property_get', '-d %d -n %s' % (self.curstack,  name))

  def watch_execute(self):
    """ execute command in watch window """
    (cmd, expr) = self.ui.watchwin.get_command()
    if cmd == 'exec':
      self.command('exec', '', expr)
      print cmd, '--', expr
    elif cmd == 'eval':
      self.command('eval', '', expr)
      print cmd, '--', expr
    elif cmd == 'property_get':
      self.command('property_get', '-d %d -n %s' % (self.curstack,  expr))
      print cmd, '-n ', expr
    elif cmd == 'context_get':
      self.command('context_get', ('-d %d' % self.curstack))
      print cmd
    else:
      print "no commands", cmd, expr

class DbgSilentClient(Thread):
  def __init__(self, ss):
    self.session = ss
    Thread.__init__(self)
  def run(self):
    self.session.init()
    self.session.sock.settimeout(None)

    resDom = self.session.command("run")
    status = "stopping"
    if resDom.firstChild.hasAttribute('status'):
      status = resDom.firstChild.getAttribute('status')
    if status == "stopping":
      self.session.command("stop")
    elif status == "break":
      dbgPavim.debugListener.newSession(self.session)

class DbgListener(Thread):
  (INIT,LISTEN,CLOSED) = (0,1,2)
  """ DBGp Procotol class """
  def __init__(self, port):
    self.port     = port
    self.session_queue = []
    self._status  = self.INIT
    self.lock = Lock()
    Thread.__init__(self)
  def start(self):
    Thread.start(self)
    time.sleep(0.1)
    dbgPavim.updateStatusLine()
  def pendingCount(self):
    self.lock.acquire()
    c = len(self.session_queue)
    self.lock.release()
    return c
  def newSession(self, ss):
    if not isinstance(ss, DbgSessionWithUI):
      s = DbgSessionWithUI(None)
      s.copyFromParent(ss)
      ss = s
    self.lock.acquire()
    self.session_queue.append(ss)
    c = str(len(self.session_queue))
    self.lock.release()
    dbgPavim.updateStatusLine()
    print c+" pending connection(s) to be debug, press "+dbgPavim.dbgPavimKeyRun+" to continue."
  def nextSession(self):
    session = None
    self.lock.acquire()
    if len(self.session_queue) > 0:
      session = self.session_queue.pop(0)
    self.lock.release()
    dbgPavim.updateStatusLine()
    print ""
    return session
  def stop(self):
    self.lock.acquire()
    try:
      if self._status == self.LISTEN:
        client = socket.socket ( socket.AF_INET, socket.SOCK_STREAM )
        client.connect ( ( '127.0.0.1', self.port ) )
        client.close()
      for s in self.session_queue:
        s.send_command('detach')
        s.sock.close()
      del self.session_queue[:]
    finally:
      self._status = self.CLOSED
      self.lock.release()
      dbgPavim.updateStatusLine()
  def status(self):
    self.lock.acquire()
    s = self._status
    self.lock.release()
    return s
  def run(self):
    global dbgPavim
    self.lock.acquire()
    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serv.settimeout(None)
    try:
      serv.bind(('', self.port))
    except socket.error, e:
      print "Can not bind to port "+str(self.port)+', Socket Error '+str(e[0])
      self.lock.release()
      return
    print ""
    serv.listen(5)
    self._status = self.LISTEN
    self.lock.release()
    while 1:
      (sock, address) = serv.accept()
      s = self.status()
      if s == self.LISTEN:
        if dbgPavim.break_at_entry:
          self.newSession(DbgSessionWithUI(sock))
        else:
          client = DbgSilentClient(DbgSession(sock))
          client.start()
      else:
        break
    serv.close()

class BreakPoint:
  """ Breakpoint class """
  def __init__(self):
    """ initalize """
    self.dictionaries  = {}
    self.startbno = 10000
    self.maxbno   = self.startbno
  def clear(self):
    """ clear of breakpoint number """
    self.dictionaries.clear()
    self.maxbno = self.startbno
  def add(self, file, line, exp = ''):
    """ add break point at file:line """
    self.maxbno = self.maxbno + 1
    self.dictionaries[self.maxbno] = { 'file':file, 'line':line, 'exp':exp }
    return self.maxbno
  def remove(self, bno):
    """ remove break point numbered with bno """
    del self.dictionaries[bno]
  def find(self, file, line):
    """ find break point and return bno(breakpoint number) """
    for bno in self.dictionaries.keys():
      if self.dictionaries[bno]['file'] == file and self.dictionaries[bno]['line'] == line:
        return bno
    return None
  def getfile(self, bno):
    """ get file name of breakpoint numbered with bno """
    return self.dictionaries[bno]['file']
  def getline(self, bno):
    """ get line number of breakpoint numbered with bno """
    return self.dictionaries[bno]['line']
  def getexp(self, bno):
    """ get expression of breakpoint numbered with bno """
    return self.dictionaries[bno]['exp']
  def list(self):
    """ return list of breakpoint number """
    return self.dictionaries.keys()

class AsyncRunner(Thread):
  def __init__(self, cmd, logfile):
    self.cmd = cmd
    self.logfile = logfile
    Thread.__init__(self)
  def run(self):
    log = open(self.logfile, "w")
    subprocess.check_call(self.cmd, stdin=None, stdout=log, stderr=log, shell=True)
    log.close()
    os.remove(self.logfile)

class DBGPavim:
  """ Main DBGPavim class """
  def __init__(self):
    """ initialize DBGPavim """
    self.loadSettings()
    self.debugListener = DbgListener(self.port)
    self.debugSession  = DbgSession(None)
    vim.command('sign unplace *')

    self.normal_statusline = vim.eval('&statusline')
    self.statusline="%<%f\ %h%m%r\ %=%-10.(%l,%c%V%)\ %P\ %=%{'PHP-'}%{(g:dbgPavimBreakAtEntry==1)?'bae':'bap'}"
    self.breakpt    = BreakPoint()
    self.ui         = DebugUI(12, 70)
    self.watchList  = []

  def updateStatusLine(self):
    status = self.debugListener.status()
    if status == DbgListener.INIT or status == DbgListener.CLOSED:
      sl = self.normal_statusline
    else:
      c = self.debugListener.pendingCount()
      if c > 0:
        sl = self.statusline+"%{'-PEND"+str(c)+"'}"
      elif self.debugSession.sock != None:
        sl = self.statusline+"%{'-CONN'}"
      else:
        sl = self.statusline+"%{'-LISN'}"
    vim.command("let &statusline=\""+sl+"\"")

  def loadSettings(self):
    self.port = int(vim.eval('dbgPavimPort'))
    self.dbgPavimKeyRun = vim.eval('dbgPavimKeyRun')
    self.max_children = vim.eval('dbgPavimMaxChildren')
    self.max_data = vim.eval('dbgPavimMaxData')
    self.max_depth = vim.eval('dbgPavimMaxDepth')
    self.break_at_entry = int(vim.eval('dbgPavimBreakAtEntry'))
    self.show_context = int(vim.eval('dbgPavimShowContext'))
    self.path_map = vim.eval('dbgPavimPathMap')
    for m in self.path_map:
      m[0] = m[0].replace("\\","/")
      m[1] = m[1].replace("\\","/")
  def remotePathOf(self,lpath):
    for m in self.path_map:
      l = len(m[0])
      if l and lpath[0:l] == m[0]:
        return m[1]+lpath[l:]
    return lpath
  def localPathOf(self,rpath):
    for m in self.path_map:
      l = len(m[1])
      if l and rpath[0:l] == m[1]:
        return m[0]+rpath[l:]
    return rpath
  def setMaxChildren(self):
    self.max_children = vim.eval('dbgPavimMaxChildren')
    if self.debugSession.sock != None:
      self.debugSession.command('feature_set', '-n max_children -v ' + self.max_children)
  def setMaxDepth(self):
    self.max_depth = vim.eval('dbgPavimMaxDepth')
    if self.debugSession.sock != None:
      self.debugSession.command('feature_set', '-n max_depth -v ' + self.max_depth)
  def setMaxData(self):
    self.max_data = vim.eval('dbgPavimMaxData')
    if self.debugSession.sock != None:
      self.debugSession.command('feature_set', '-n max_data -v ' + self.max_data)
  def handle_exception(self):
    if self.ui.tracewin:
      self.ui.tracewin.write(sys.exc_info())
      self.ui.tracewin.write("".join(traceback.format_tb( sys.exc_info()[2])))
    errno = sys.exc_info()[0]

    session = self.debugListener.nextSession()
    if errno == socket.timeout:
      if session != None:
        print "socket timeout, switch to another session."
        ss = DbgSession(self.debugSession.sock)
        ss.latestRes = self.debugSession.latestRes
        client = DbgSilentClient(ss)
        client.start()
        self.debugSession = session
        self.debugSession.start()
      else:
        print "socket timeout, try again or press F6 to stop debugging."
    else: #errno == socket.error:
      self.debugSession.close()
      if session != None:
        self.debugSession = session
        self.debugSession.start()
      else:
        self.ui.normal_mode()
    self.updateStatusLine()
  def command(self, msg, arg1 = '', arg2 = ''):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
        self.debugSession.command(msg, arg1, arg2)
        if self.debugSession.status != 'stopping':
          self.debugSession.command('stack_get')
          for var in self.watchList:
            self.debugSession.command('property_get', "-d %d -n %s" % (self.debugSession.curstack, var))
          if self.show_context:
            self.debugSession.command('context_get', ('-d %d' % self.debugSession.curstack))
        else:
          self.debugSession.command('stop')
    except:
      self.handle_exception()
  def watch_input(self, cmd, arg = ''):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
        if arg == '<cword>':
          arg = vim.eval('expand("<cword>")')
        if arg == 'this':
          arg = '$this'
        self.debugSession.watch_input(cmd, arg)
    except:
      self.handle_exception()
  def watch(self, name = ''):
    if name == '':
      self.show_context = not self.show_context
    else:
      if name in self.watchList:
        self.watchList.remove(name)
      else:
        self.watchList.append(name)
  def listWatch(self):
    if self.show_context:
      print '*CONTEXT*'
    for var in self.watchList:
      print var;
  def property(self, name = ''):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
        string.replace(name,'"','\'')
        if string.find(name,' ') != -1:
          name = "\"" + name +"\""
        elif name == 'this':
          name = '$this'
        self.debugSession.property_get(name)
    except:
      self.handle_exception()
  def up(self):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
        self.debugSession.up()
    except:
      self.handle_exception()

  def down(self):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
        self.debugSession.down()
    except:
      self.handle_exception()

  def run(self):
    """ start debugger or continue """
    try:
      status = self.debugListener.status()
      if status == DbgListener.INIT or status == DbgListener.CLOSED:
        self.loadSettings()
        self.debugListener = DbgListener(self.port)
        self.debugListener.start()
      elif self.debugSession.sock != None:
        self.debugSession.command('run')
        if self.debugSession.status == 'stopping':
          self.debugSession.command("stop")
        elif self.debugSession.status != 'stopped':
          self.debugSession.command("stack_get")
      else:
        session = self.debugListener.nextSession()
        if session != None:
          self.debugSession = session
          self.debugSession.start()
    except:
      self.handle_exception()

  def cli(self, args):
    vim.command("let g:dbgPavimBreakAtEntry=1")
    self.ui.cliwin = ConsoleWindow(self.ui.clilog)
    self.run()
    filetype = vim.eval('&filetype')
    filename = vim.eval('expand("%")')
    if filename:
      cmd = ' '+filename+' '+args
      if filetype == 'php':
        if vim.eval('CheckXdebug()') == '0':
          cmd = 'php -dxdebug.remote_autostart=1 -dxdebug.remote_port='+str(self.port)+cmd
      elif filetype == 'python':
        if vim.eval('CheckPydbgp()') == '0':
          cmd = 'pydbgp -u -d '+str(self.port)+cmd
      if cmd[0] != ' ':
        ar = AsyncRunner(cmd, self.ui.clilog)
        ar.start()
        time.sleep(0.4)
        vim.eval('feedkeys("\\'+self.dbgPavimKeyRun+'")')
      else:
        print "Only python and php file debugging are integrated for now."
    else:
      print "You need open one python or php file first."

  def list(self):
    self.ui.watchwin.write('// breakpoints list: ')
    for bno in self.breakpt.list():
      self.ui.watchwin.write(str(bno)+'  ' + self.breakpt.getfile(bno) + ':' + str(self.breakpt.getline(bno)))

  def mark(self, exp = ''):
    (row, rol) = vim.current.window.cursor
    file       = vim.current.buffer.name

    bno = self.breakpt.find(file, row)
    if bno != None:
      self.breakpt.remove(bno)
      vim.command('sign unplace ' + str(bno))
      id = self.debugSession.getbid(bno)
      if self.debugSession.sock != None and id != None:
        self.debugSession.send_command('breakpoint_remove', '-d ' + str(id))
        self.debugSession.ack_command()
    else:
      bno = self.breakpt.add(file, row, exp)
      vim.command('sign place ' + str(bno) + ' name=breakpt line=' + str(row) + ' file=' + file)
      if self.debugSession.sock != None:
        fn = dbgPavim.remotePathOf(self.breakpt.getfile(bno))
        if self.debugSession.isWinServer:
          fn = fn.replace("/","\\")
        msgid = self.debugSession.send_command('breakpoint_set', \
                                  '-t line -f ' + fn + ' -n ' + str(self.breakpt.getline(bno)), \
                                  self.breakpt.getexp(bno))
        self.debugSession.bptsetlst[msgid] = bno
        self.debugSession.ack_command()

  def quit(self):
    if self.debugSession.sock:
      self.debugSession.send_command('detach')
    self.ui.normal_mode()
    self.debugSession.close()
    self.debugListener.stop()

def dbgPavim_init():
  global dbgPavim
  dbgPavim = DBGPavim()

error_msg = { \
    # 000 Command parsing errors
    0   : """no error""",                                                                                                                                                      \
    1   : """parse error in command""",                                                                                                                                        \
    2   : """duplicate arguments in command""",                                                                                                                                \
    3   : """invalid options (ie, missing a required option)""",                                                                                                               \
    4   : """Unimplemented command""",                                                                                                                                         \
    5   : """Command not available (Is used for async commands. For instance if the engine is in state "run" than only "break" and "status" are available). """,               \
    # 100 : File related errors
    100 : """can not open file (as a reply to a "source" command if the requested source file can't be opened)""",                                                             \
    101 : """stream redirect failed """,                                                                                                                                       \
    # 200 Breakpoint, or code flow errors
    200 : """breakpoint could not be set (for some reason the breakpoint could not be set due to problems registering it)""",                                                  \
    201 : """breakpoint type not supported (for example I don't support 'watch' yet and thus return this error)""",                                                            \
    202 : """invalid breakpoint (the IDE tried to set a breakpoint on a line that does not exist in the file (ie "line 0" or lines past the end of the file)""",               \
    203 : """no code on breakpoint line (the IDE tried to set a breakpoint on a line which does not have any executable code. The debugger engine is NOT required to """     + \
          """return this type if it is impossible to determine if there is code on a given location. (For example, in the PHP debugger backend this will only be """         + \
          """returned in some special cases where the current scope falls into the scope of the breakpoint to be set)).""",                                                    \
    204 : """Invalid breakpoint state (using an unsupported breakpoint state was attempted)""",                                                                                                                                                      \
    205 : """No such breakpoint (used in breakpoint_get etc. to show that there is no breakpoint with the given ID)""",                                                        \
    206 : """Error evaluating code (use from eval() (or perhaps property_get for a full name get))""",                                                                         \
    207 : """Invalid expression (the expression used for a non-eval() was invalid) """,                                                                                        \
    # 300 Data errors
    300 : """Can not get property (when the requested property to get did not exist, this is NOT used for an existing but uninitialized property, which just gets the """    + \
          """type "uninitialised" (See: PreferredTypeNames)).""",                                                                                                              \
    301 : """Stack depth invalid (the -d stack depth parameter did not exist (ie, there were less stack elements than the number requested) or the parameter was < 0)""",      \
    302 : """Context invalid (an non existing context was requested) """,                                                                                                      \
    # 900 Protocol errors
    900 : """Encoding not supported""",                                                                                                                                        \
    998 : """An internal exception in the debugger occurred""",                                                                                                                \
    999 : """Unknown error """                                                                                                                                                 \
}

