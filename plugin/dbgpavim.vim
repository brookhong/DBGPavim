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
"               on port 9000. You can change this with the g:dbgPavimPort
"               variable by putting the following line your vimrc:
"
"                 let g:dbgPavimPort = 10001
"
"               where 10001 is the new port number you want the server to
"               connect to.
"
"               There are three maximum limits you can set referring to the
"               properties (variables) returned by the debugging engine.
"
"               g:dbgPavimMaxChildren (default 1024): The max number of array or
"               object children to initially retrieve per variable.
"               For example:
"
"                 let g:dbgPavimMaxChildren = 64
"
"               g:dbgPavimMaxData (default 1024 bytes): The max amount of
"               variable data to retrieve.
"               For example:
"
"                 let g:dbgPavimMaxData = 2048
"
"               g:dbgPavimMaxDepth (default 1): The maximum depth that the
"               debugger engine may return when sending arrays, hashs or
"               object structures to the IDE.
"               For example:
"
"                 let g:dbgPavimMaxDepth = 10
"
"               g:dbgPavimBreakAtEntry (default 0): Whether to break at entry,
"               if set it 0, the debugger engine will break only at
"               breakpoints.
"               For example:
"
"                 let g:dbgPavimBreakAtEntry = 1
"
"               g:dbgPavimPathMap (default []): Map local path to remote path
"               on server.
"               For example:
"
"                 let g:dbgPavimPathMap = [['D:/works/php','/var/www'],]
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

if !exists('g:dbgPavimPort')
  let g:dbgPavimPort = 9000
endif
if !exists('g:dbgPavimMaxChildren')
  let g:dbgPavimMaxChildren = 1024
endif
if !exists('g:dbgPavimMaxData')
  let g:dbgPavimMaxData = 1024
endif
if !exists('g:dbgPavimMaxDepth')
  let g:dbgPavimMaxDepth = 1
endif
if !exists('g:dbgPavimBreakAtEntry')
  let g:dbgPavimBreakAtEntry = 0
endif
if !exists('g:dbgPavimPathMap')
  let g:dbgPavimPathMap = []
endif
map <silent> <F5> :python dbgPavim.run()<cr>
map <silent> <F6> :python dbgPavim.quit()<cr>
map <silent> <F8> :call Bae()<cr>
map <silent> + :call ResizeWindow("+")<cr>
map <silent> - :call ResizeWindow("-")<cr>
command! -nargs=? Bp python dbgPavim.mark('<args>')
command! -nargs=0 Bl python dbgPavim.list()
command! -nargs=? Dp python dbgPavim.cli('<args>')
command! -nargs=1 Children let g:dbgPavimMaxChildren=<args>|python dbgPavim.setMaxChildren()
command! -nargs=1 Depth let g:dbgPavimMaxDepth=<args>|python dbgPavim.setMaxDepth()
command! -nargs=1 Length let g:dbgPavimMaxData=<args>|python dbgPavim.setMaxData()

function! CreateFunctionKeys()
  map <silent> <F1> :python dbgPavim.ui.help()<cr>
  map <silent> <F2> :python dbgPavim.command('step_into')<cr>
  map <silent> <F3> :python dbgPavim.command('step_over')<cr>
  map <silent> <F4> :python dbgPavim.command('step_out')<cr>
  map <silent> <F7> :python dbgPavim.watch_input("eval")<cr>A
  map <silent> <F9> :python dbgPavim.ui.reLayout()<cr>
  map <silent> <F11> :python dbgPavim.watch_input("context_get")<cr>A<cr>
  map <silent> <F12> :python dbgPavim.watch_input("property_get", '<cword>')<cr>A<cr>
  map U u2<C-o>z.

  command! -nargs=0 Up python dbgPavim.up()
  command! -nargs=0 Dn python dbgPavim.down()
  command! -nargs=? Pg python dbgPavim.property("<args>")
  command! -nargs=0 Dt python dbgPavim.ui.trace()
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
    unmap U

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
  let g:dbgPavimBreakAtEntry = (g:dbgPavimBreakAtEntry == 1) ? 0 : 1
  execute 'python dbgPavim.break_at_entry = '.g:dbgPavimBreakAtEntry
endfunction
function! WatchWindowOnEnter()
  let l:line = getline(".")
  if l:line =~ "^\\s*\\$.* = (object) $\\|(array) $"
    execute "Pg ".substitute(line,"\\s*\\(\\S.*\\S\\)\\s*=.*","\\1","g")
    execute "normal \<c-w>p"
  elseif l:line =~ "^\\d\\+  .*:\\d\\+$"
    let fn = substitute(l:line,"^\\d\\+  \\(.*\\):\\d\\+$","\\1","")
    let ln = substitute(l:line,"^\\d\\+  .*:\\(\\d\\+\\)$","\\1","")
    execute 'python dbgPavim.debugSession.jump("'.l:fn.'",'.l:ln.')'
  elseif foldlevel(".") > 0
    execute 'normal za'
  endif
endfunction
function! StackWindowOnEnter()
  let l:stackNo = substitute(getline("."),"\\(\\d\\+\\)\\s\\+.*","\\1","g")
  if l:stackNo =~ "^\\d\\+$" 
    execute 'python dbgPavim.debugSession.go('.l:stackNo.')'
    execute "normal \<c-w>p"
  endif
endfunction

hi DbgCurrent term=reverse ctermfg=White ctermbg=Red gui=reverse
hi DbgBreakPt term=reverse ctermfg=White ctermbg=Green gui=reverse
sign define current text=->  texthl=DbgCurrent linehl=DbgCurrent
sign define breakpt text=B>  texthl=DbgBreakPt linehl=DbgBreakPt

python dbgPavim_init()
set laststatus=2

autocmd BufEnter WATCH_WINDOW map <silent> <buffer> <Enter> :call WatchWindowOnEnter()<CR>
autocmd BufEnter STACK_WINDOW map <silent> <buffer> <Enter> :call StackWindowOnEnter()<CR>
autocmd BufLeave HELP__WINDOW :python dbgPavim.ui.helpwin=None
autocmd VimLeavePre * python dbgPavim.quit()
