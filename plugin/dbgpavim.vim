" vim: tabstop=2 shiftwidth=2 softtabstop=2 expandtab
" DBGPavim: a remote debugger interface to the DBGp protocol
"
" Script Info and Documentation  {{{
"=============================================================================
"    Copyright: Copyright (C) 2012 Brook Hong
"      License:	The MIT License
"				
"				Permission is hereby granted, free of charge, to any person obtaining
"				a copy of this software and associated documentation files
"				(the "Software"), to deal in the Software without restriction,
"				including without limitation the rights to use, copy, modify,
"				merge, publish, distribute, sublicense, and/or sell copies of the
"				Software, and to permit persons to whom the Software is furnished
"				to do so, subject to the following conditions:
"				
"				The above copyright notice and this permission notice shall be included
"				in all copies or substantial portions of the Software.
"				
"				THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
"				OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
"				MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
"				IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
"				CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
"				TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
"				SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
" Name Of File: dbgpavim.vim, dbgpavim.py
"  Description: remote debugger interface to DBGp protocol
"               The DBGPavim originates from http://www.vim.org/scripts/script.php?script_id=1152, with a new enhanced debugger engine.
"
"               This file should reside in the plugins directory along
"               with dbgpavim.py and be automatically sourced.
"               
"               By default, the script expects the debugging engine to connect
"               on port 9000. You can change this with the g:debuggerPort
"               variable by putting the following line your vimrc:
"
"                 let g:debuggerPort = 10001
"
"               where 10001 is the new port number you want the server to
"               connect to.
"
"               There are three maximum limits you can set referring to the
"               properties (variables) returned by the debugging engine.
"
"               g:debuggerMaxChildren (default 1024): The max number of array or
"               object children to initially retrieve per variable.
"               For example:
"
"                 let g:debuggerMaxChildren = 64
"
"               g:debuggerMaxData (default 1024 bytes): The max amount of
"               variable data to retrieve.
"               For example:
"
"                 let g:debuggerMaxData = 2048
"
"               g:debuggerMaxDepth (default 1): The maximum depth that the
"               debugger engine may return when sending arrays, hashs or
"               object structures to the IDE.
"               For example:
"
"                 let g:debuggerMaxDepth = 10
"
"               g:debuggerBreakAtEntry (default 1): Whether to break at entry,
"               if set it 0, the debugger engine will break only at
"               breakpoints.
"               For example:
"
"                 let g:debuggerBreakAtEntry = 0
"
"               To enable debug from CLI
"
"                 php -dxdebug.remote_autostart=1 -dxdebug.remote_port=9000 test.php
"=============================================================================
" }}}
" Do not source this script when python is not compiled in.
if !has("python")
    finish
endif

" Load dbgpavim.py either from the same path where dbgpavim.vim is
let s:dbgpavim_py = expand("<sfile>:p:h")."/dbgpavim.py"
if filereadable(s:dbgpavim_py)
  exec 'pyfile '.s:dbgpavim_py 
else
  call confirm('dbgpavim.vim: Unable to find '.s:dbgpavim_py.'. Place it in either your home vim directory or in the Vim runtime directory.', 'OK')
endif

map <silent> <F5> :python debugger.run()<cr>
map <silent> <F6> :python debugger.quit()<cr>
map <silent> <F8> :call Bae()<cr>
map <silent> + :call ResizeWindow("+")<cr>
map <silent> - :call ResizeWindow("-")<cr>
command! -nargs=? Bp python debugger.mark('<args>')
command! -nargs=0 Bl python debugger.list()
command! -nargs=1 Dmc let g:debuggerMaxChildren=<args>|python debugger.setMaxChildren()
command! -nargs=1 Dme let g:debuggerMaxDepth=<args>|python debugger.setMaxDepth()
command! -nargs=1 Dma let g:debuggerMaxData=<args>|python debugger.setMaxData()
function! CreateFunctionKeys()
  map <silent> <F1> :python debugger.ui.help()<cr>
  map <silent> <F2> :python debugger.command('step_into')<cr>
  map <silent> <F3> :python debugger.command('step_over')<cr>
  map <silent> <F4> :python debugger.command('step_out')<cr>
  map <silent> <F7> :python debugger.watch_input("eval")<cr>A
  map <silent> <F9> :python debugger.ui.reLayout()<cr>
  map <silent> <F11> :python debugger.watch_input("context_get")<cr>A<cr>
  map <silent> <F12> :python debugger.watch_input("property_get", '<cword>')<cr>A<cr>
  
  command! -nargs=0 Up python debugger.up()
  command! -nargs=0 Dn python debugger.down()
  command! -nargs=? Pg python debugger.property("<args>")
  command! -nargs=0 Dt python debugger.ui.trace()
endfunction
function! ClearFunctionKeys()
  try
    unmap <F1>
    unmap <F2>
    unmap <F3>
    unmap <F4>
    unmap <F7>
    unmap <F9>
    unmap <F11>
    unmap <F12>
  
    delcommand Up
    delcommand Dn
    delcommand Pg
	catch /.*/
	  echo "Exception from" v:throwpoint
	endtry
endfunction
function! ResizeWindow(flag)
  let l:width = winwidth("%")
  if l:width == &columns
    execute 'resize '.a:flag.'5'
  else
    execute 'vertical resize '.a:flag.'5'
  endif
endfunction
function! Bae()
  let g:debuggerBreakAtEntry = (g:debuggerBreakAtEntry == 1) ? 0 : 1
  execute 'python debugger.break_at_entry = '.g:debuggerBreakAtEntry
endfunction
function! WatchWindowOnEnter()
  let l:line = getline(".")
  if l:line =~ "^\\s*\\$.* = (object)\\|(array)"
    execute "Pg ".substitute(line,"\\s*\\(\\S.*\\S\\)\\s*=.*","\\1","g")
    execute "normal \<c-w>p"
  elseif l:line =~ "^\\d\\+  .*:\\d\\+$"
    let fn = substitute(l:line,"^\\d\\+  \\(.*\\):\\d\\+$","\\1","")
    let ln = substitute(l:line,"^\\d\\+  .*:\\(\\d\\+\\)$","\\1","")
    execute 'python debugger.debugSession.jump("'.l:fn.'",'.l:ln.')'
  endif
endfunction
function! StackWindowOnEnter()
  let l:stackNo = substitute(getline("."),"\\(\\d\\+\\)\\s\\+.*","\\1","g")
  if l:stackNo =~ "^\\d\\+$" 
    execute 'python debugger.debugSession.go('.l:stackNo.')'
    execute "normal \<c-w>p"
  endif
endfunction

hi DbgCurrent term=reverse ctermfg=White ctermbg=Red gui=reverse
hi DbgBreakPt term=reverse ctermfg=White ctermbg=Green gui=reverse
sign define current text=->  texthl=DbgCurrent linehl=DbgCurrent
sign define breakpt text=B>  texthl=DbgBreakPt linehl=DbgBreakPt

if !exists('g:debuggerPort')
  let g:debuggerPort = 9000
endif
if !exists('g:debuggerMaxChildren')
  let g:debuggerMaxChildren = 1024
endif
if !exists('g:debuggerMaxData')
  let g:debuggerMaxData = 1024
endif
if !exists('g:debuggerMaxDepth')
  let g:debuggerMaxDepth = 1
endif
if !exists('g:debuggerBreakAtEntry')
  let g:debuggerBreakAtEntry = 1
endif
python debugger_init()
set laststatus=2

autocmd BufEnter WATCH_WINDOW map <silent> <buffer> <Enter> :call WatchWindowOnEnter()<CR>
autocmd BufEnter STACK_WINDOW map <silent> <buffer> <Enter> :call StackWindowOnEnter()<CR>
autocmd BufLeave HELP__WINDOW :python debugger.ui.helpwin=None
autocmd VimLeavePre * python debugger.quit()
