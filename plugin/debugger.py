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
#    Sam Ghods <sam <at> box.net>
#    I rewrote it with a new debugger engine, please diff this file to find code change.

"""
    debugger.py -- DBGp client: a remote debugger interface to DBGp protocol

    Usage:
        Use with the debugger.vim vim plugin

    This debugger is designed to be used with debugger.vim,
    a vim plugin which provides a full debugging environment
    right inside vim.

    CHECK DEBUGGER.VIM FOR THE FULL DOCUMENTATION.

    Example usage:
        Place inside <source vim directory>/plugin/ along with
        debugger.py.
"""

import os
import sys
import vim
import socket
import base64
import traceback
import xml.dom.minidom

from threading import Thread,Lock

class VimWindow:
  """ wrapper class of window of vim """
  def __init__(self, name = 'DEBUG_WINDOW'):
    """ initialize """
    self.name       = name
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
      self.create()
  def on_create(self):
    pass
  def getwinnr(self):
    return int(vim.eval("bufwinnr('"+self.name+"')"))

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
      if sys.platform == 'win32':
        fn = node.getAttribute('filename')[8:]
      else:
        fn = node.getAttribute('filename')[7:]
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

class LogWindow(VimWindow):
  def __init__(self, name = 'LOG___WINDOW'):
    VimWindow.__init__(self, name)
  def on_create(self):
    self.command('set nowrap fdm=marker fmr={{{,}}} fdl=0')
    self.write('asdfasdf')

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
    self.command('set nowrap fdm=marker fmr={{{,}}} fdl=0')

class WatchWindow(VimWindow):
  def __init__(self, name = 'WATCH_WINDOW'):
    VimWindow.__init__(self, name)
  def fixup_single(self, line, node, level):
    return ''.ljust(level*1) + line + '\n'
  def fixup_childs(self, line, node, level):
    global z
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
        line = ''.ljust(level*1) + str(line) + ';' + '\n'
        line += self.xml_stringfy_childs(node, level+1)
        line += '/*}}}1*/\n'
      else:
        line = (''.ljust(level*1) + str(line) + ';').ljust(self.width-20) + ''.ljust(level*1) + '/*{{{' + str(level+1) + '*/' + '\n'
        line += str(self.xml_stringfy_childs(node, level+1))
        line += (''.ljust(level*1) + ''.ljust(level*1)).ljust(self.width-20) + ''.ljust(level*1) + '/*}}}' + str(level+1) + '*/\n'
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
      return "$command = '" + node.getAttribute('command') + "'"
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
    self.command('inoremap <buffer> <cr> <esc>:python debugger.debugSession.watch_execute()<cr>')
    self.command('set noai nocin')
    self.command('set nowrap fdm=marker fmr={{{,}}} ft=php fdl=1')
  def input(self, mode, arg = ''):
    line = self.buffer[-1]
    if line[:len(mode)+1] == '/*{{{1*/ => '+mode+':':
      self.buffer[-1] = line + arg
    else:
      self.buffer.append('/*{{{1*/ => '+mode+': '+arg)
    self.command('normal G')
  def get_command(self):
    line = self.buffer[-1]
    if line[0:17] == '/*{{{1*/ => exec:':
      print "exec does not supported by xdebug now."
      return ('none', '')
      #return ('exec', line[17:].strip(' '))
    elif line[0:17] == '/*{{{1*/ => eval:':
      return ('eval', line[17:].strip(' '))
    elif line[0:25] == '/*{{{1*/ => property_get:':
      return ('property_get', line[25:].strip(' '))
    elif line[0:24] == '/*{{{1*/ => context_get:':
      return ('context_get', line[24:].strip(' '))
    else:
      return ('none', '')

class HelpWindow(VimWindow):
  def __init__(self, name = 'HELP__WINDOW'):
    VimWindow.__init__(self, name)
  def on_create(self):
    self.write(                                                          \
        '[ Function Keys ]                 |                       \n' + \
        '  <F1>   resize                   | [ Normal Mode ]       \n' + \
        '  <F2>   step into                |   ,pe  eval           \n' + \
        '  <F3>   step over                |                       \n' + \
        '  <F4>   step out                 | [ Command Mode ]      \n' + \
        '  <F5>   run                      | :Bp toggle breakpoint \n' + \
        '  <F6>   quit debugging           | :Up stack up          \n' + \
        '                                  | :Dn stack down        \n' + \
        '  <F11>  get all context          | :Bl list breakpoints  \n' + \
        '  <F12>  get property at cursor   | :Pg property get      \n' + \
        '\n')
    self.command('1')

class DebugUI:
  """ DEBUGUI class """
  def __init__(self):
    """ initialize object """
    self.watchwin = WatchWindow()
    self.stackwin = StackWindow()
    self.tracewin = TraceWindow()
    self.helpwin  = HelpWindow('HELP__WINDOW')
    self.mode     = 0 # normal mode
    self.file     = None
    self.line     = None
    self.winbuf   = {}
    self.cursign  = None
    if sys.platform == 'win32':
      self.sessfile = "./debugger_vim_saved_session." + str(os.getpid())
    else:
      self.sessfile = "/tmp/debugger_vim_saved_session." + str(os.getpid())

  def debug_mode(self):
    """ change mode to debug """
    if self.mode == 1: # is debug mode ?
      return
    self.mode = 1
    # save session
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

  def normal_mode(self):
    """ restore mode to normal """
    if self.mode == 0: # is normal mode ?
      return

    vim.command('sign unplace 1')
    vim.command('sign unplace 2')

    # destory all created windows
    self.destroy()

    # restore session
    vim.command('silent tabonly')
    vim.command('source ' + self.sessfile)
    os.system('rm -f ' + self.sessfile)

    self.set_highlight()


    self.winbuf.clear()
    self.file    = None
    self.line    = None
    self.mode    = 0
    self.cursign = None
  def create(self):
    """ create windows """
    self.watchwin.create('vertical belowright new')
    self.helpwin.create('belowright new')
    self.stackwin.create('belowright new')
    self.tracewin.create('belowright new')

  def set_highlight(self):
    """ set vim highlight of debugger sign """
    vim.command("highlight DbgCurrent term=reverse ctermfg=White ctermbg=Red gui=reverse")
    vim.command("highlight DbgBreakPt term=reverse ctermfg=White ctermbg=Green gui=reverse")

  def destroy(self):
    """ destroy windows """
    self.helpwin.destroy()
    self.watchwin.destroy()
    self.stackwin.destroy()
    self.tracewin.destroy()
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

    nextsign = self.next_sign()

    if file != self.file:
      self.file = file
      self.go_srcview()
      vim.command('silent edit ' + file)

    vim.command('sign place ' + nextsign + ' name=current line='+str(line)+' file='+file)
    vim.command('sign unplace ' + self.cursign)

    vim.command('sign jump ' + nextsign + ' file='+file)
    #vim.command('normal z.')

    self.line    = line
    self.cursign = nextsign

class DbgSession:
  def __init__(self, sock):
    self.latestRes = None
    self.msgid = 0
    self.sock = sock
    self.bptsetlst  = {} 
    self.bptsetids  = {} 
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
    try:
      length = self.recv_length()
      body   = self.recv_body(length)
      self.recv_null()
      return body
    except socket.error, e:
      # WINDOWS come here
      if e[0] == 10053:
        raise EOFError, 'Socket Closed'
      else:
        raise EOFError, 'Socket Error '+str(e[0])
  def send_msg(self, cmd):
    self.sock.send(cmd + '\0')
  def handle_recvd_msg(self, res):
    resDom = xml.dom.minidom.parseString(res)
    #debugger.ui.tracewin.write(res)
    if resDom.firstChild.tagName == "response" and resDom.firstChild.getAttribute('command') == "breakpoint_set":
      self.handle_response_breakpoint_set(resDom)
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
    self.ack_command(1)
    flag = 0
    for bno in debugger.breakpt.list():
      msgid = self.send_command('breakpoint_set', \
                                '-t line -f ' + debugger.breakpt.getfile(bno) + ' -n ' + str(debugger.breakpt.getline(bno)) + ' -s enabled', \
                                debugger.breakpt.getexp(bno))
      self.bptsetlst[msgid] = bno
      flag = 1
    if flag:
      self.ack_command()

class DbgSessionWithUI(DbgSession):
  def __init__(self, sock):
    self.status     = None
    self.ui         = debugger.ui

    self.msgid      = 0
    self.stacks     = []
    self.curstack   = 0
    self.laststack  = 0
    DbgSession.__init__(self,sock)
  def copyFromParent(self, ss):
    self.latestRes = ss.latestRes
    self.msgid = ss.msgid
    self.sock = ss.sock
    self.bptsetlst  = ss.bptsetlst
    self.bptsetids  = ss.bptsetids
  def init(self):
    DbgSession.init(self)
    self.command('feature_set', '-n max_children -v ' + debugger.max_children)
    self.command('feature_set', '-n max_data -v ' + debugger.max_data)
    self.command('feature_set', '-n max_depth -v ' + debugger.max_depth)
    self.command('step_into')
    self.command('property_get', "-n $_SERVER['REQUEST_URI']")
  def start(self):
    debugger.updateStatusLine("--CONN")
    self.ui.debug_mode()

    if self.latestRes != None:
      self.handle_recvd_msg(self.latestRes)
      self.command('stack_get')
      self.command('property_get', "-n $_SERVER['REQUEST_URI']")
    else:
      self.init()
    self.ui.go_srcview()
  def send_msg(self, cmd):
    """ send message """
    self.sock.send(cmd + '\0')
    # log message
    if debugger.debug:
      self.ui.tracewin.write(str(self.msgid) + ' : send =====> ' + cmd)
  def handle_recvd_msg(self, txt):
    # log messages {{{
    if debugger.debug:
      self.ui.tracewin.write( str(self.msgid) + ' : recv <===== {{{   ' + txt)
      self.ui.tracewin.write('}}}')
    res = xml.dom.minidom.parseString(txt)
    """ call appropraite message handler member function, handle_XXX() """
    fc = res.firstChild
    try:
      handler = getattr(self, 'handle_' + fc.tagName)
      handler(res)
    except AttributeError:
      print 'Debugger.handle_'+fc.tagName+'() not found, please see the LOG___WINDOW'
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
      print 'Debugger.handle_response_'+command+'() not found, please see the LOG___WINDOW'
      return
    handler(res)
    return

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
   
    if sys.platform == 'win32':
      file = res.firstChild.getAttribute('fileuri')[8:]
    else:
      file = res.firstChild.getAttribute('fileuri')[7:]
    self.ui.set_srcview(file, 1)

  def handle_response_error(self, res):
    """ handle <error> tag """
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
    </response>"""

    stacks = res.getElementsByTagName('stack')
    if len(stacks)>0:
      self.curstack  = 0
      self.laststack = len(stacks) - 1

      self.stacks    = []
      for s in stacks:
        if sys.platform == 'win32':
          fn = s.getAttribute('filename')[8:]
        else:
          fn = s.getAttribute('filename')[7:]
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
    self.ui.watchwin.write_xml_childs(res)
  def handle_response_default(self, res):
    """handle <response command=context_get> tag """
    print res.toprettyxml()

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
    self.ui.watchwin.write('--> property_get: '+name)
    self.command('property_get', '-n '+name)
    
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
  def __init__(self, sock):
    self.session = DbgSession(sock)
    Thread.__init__(self)
  def run(self):
    self.session.init()

    resDom = self.session.command("run")
    status = "stopping"
    if resDom.firstChild.hasAttribute('status'):
      status = resDom.firstChild.getAttribute('status')
    if status == "stopping":
      self.session.command("stop")
    elif status == "break":
      debugger.debugListener.newSession(self.session)

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
    debugger.updateStatusLine("--LISN")
    Thread.start(self)
  def newSession(self, ss):
    if not isinstance(ss, DbgSessionWithUI):
      s = DbgSessionWithUI(None)
      s.copyFromParent(ss)
      ss = s
    self.lock.acquire()
    self.session_queue.append(ss)
    c = str(len(self.session_queue))
    debugger.updateStatusLine("--PEND"+c)
    self.lock.release()
    print c+" pending connection(s) to be debug, press <F5> to continue."
  def nextSession(self):
    session = None
    self.lock.acquire()
    if len(self.session_queue) > 0:
      session = self.session_queue.pop(0)
    self.lock.release()
    return session
  def stop(self):
    self.lock.acquire()
    if self._status == self.LISTEN:
      client = socket.socket ( socket.AF_INET, socket.SOCK_STREAM )
      client.connect ( ( '127.0.0.1', self.port ) )
      client.close()
    for s in self.session_queue:
      s.sock.close()
    self._status = self.CLOSED
    self.lock.release()
    debugger.updateStatusLine("--CLSD")
  def status(self):
    self.lock.acquire()
    s = self._status
    self.lock.release()
    return s
  def run(self):
    global debugger
    serv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serv.bind(('', self.port))
    serv.listen(5)
    self._status = self.LISTEN
    while 1:
      (sock, address) = serv.accept()
      s = self.status()
      if s == self.LISTEN:
        if debugger.break_at_entry:
          self.newSession(DbgSessionWithUI(sock))
        else:
          client = DbgSilentClient(sock)
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

class Debugger:
  """ Main Debugger class """
  def __init__(self):
    """ initialize Debugger """
    self.debug = 1
    self.loadSettings()
    self.debugListener = DbgListener(self.port)
    self.debugSession  = DbgSession(None)
    vim.command('sign unplace *')

    self.statusline = vim.eval('&statusline')
    if self.statusline == "":
      self.statusline="%<%f\ %h%m%r\ \[%{&ff}:%{&fenc}:%Y]\ %{getcwd()}\ %=%-10{(&expandtab)?'ExpandTab-'.&tabstop:'NoExpandTab'}\ %=%-10.(%l,%c%V%)\ %P"
    self.breakpt    = BreakPoint()
    self.ui         = DebugUI()
    self.mode       = 0
  def loadSettings(self):
    self.port = int(vim.eval('debuggerPort'))
    self.max_children = vim.eval('debuggerMaxChildren')
    self.max_data = vim.eval('debuggerMaxData')
    self.max_depth = vim.eval('debuggerMaxDepth')
    self.break_at_entry = int(vim.eval('debuggerBreakAtEntry'))
  def resize(self):
    self.mode = self.mode + 1
    if self.mode >= 3:
      self.mode = 0
  
    if self.mode == 0:
      vim.command("wincmd =")
    elif self.mode == 1:
      vim.command("wincmd |")
    if self.mode == 2:
      vim.command("wincmd _")
  def handle_exception(self):
      self.ui.tracewin.write(sys.exc_info())
      self.ui.tracewin.write("".join(traceback.format_tb( sys.exc_info()[2])))
      self.debugSession.close()
      session = self.debugListener.nextSession()
      if session != None:
        self.debugSession = session
        self.debugSession.start()
      else:
        self.ui.normal_mode()
        debugger.updateStatusLine("--LISN")
  def command(self, msg, arg1 = '', arg2 = ''):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
        self.debugSession.command(msg, arg1, arg2)
        if self.debugSession.status != 'stopping':
          self.debugSession.command('stack_get')
    except:
      self.handle_exception()
  def watch_input(self, cmd, arg = ''):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
        if arg == '<cword>':
          arg = vim.eval('expand("<cword>")')
        self.debugSession.watch_input(cmd, arg)
    except:
      self.handle_exception()
  def property(self, name = ''):
    try:
      if self.debugSession.sock == None:
        print 'No debug session started.'
      else:
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
        if self.debugSession.status != 'stopping':
          self.debugSession.command('stack_get')
      else:
        session = self.debugListener.nextSession()
        if session != None:
          self.debugSession = session
          self.debugSession.start()
    except:
      self.handle_exception()

  def list(self):
    self.ui.watchwin.write('--> breakpoints list: ')
    for bno in self.breakpt.list():
      self.ui.watchwin.write('  ' + self.breakpt.getfile(bno) + ':' + str(self.breakpt.getline(bno)))

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
        msgid = self.send_command('breakpoint_set', \
                                  '-t line -f ' + self.breakpt.getfile(bno) + ' -n ' + str(self.breakpt.getline(bno)), \
                                  self.breakpt.getexp(bno))
        self.debugSession.bptsetlst[msgid] = bno
        self.debugSession.ack_command()

  def updateStatusLine(self,msg):
    sl = self.statusline+"%{'"+msg+"'}"
    vim.command("let &statusline=\""+sl+"\"")

  def quit(self):
    self.ui.normal_mode()
    self.debugSession.close()
    self.debugListener.stop()

def debugger_init():
  global debugger
  debugger = Debugger()

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

