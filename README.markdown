This is a plugin to enable php debug in VIM with Xdebug, which is based on
http://www.vim.org/scripts/script.php?script_id=1152
http://www.vim.org/scripts/script.php?script_id=1929

## My enhancements are --

### Non blocking debugger engine.
So that VIM users do not need to wait for connection from apache server. No timeout things, users press F5 to start debugger engine, and uses his/her VIM normally. Debug engine won't stop users to interact with VIM. Users can press F6 to stop debugger engine anytime.

### Catch all connections from apache server.
This is very important for a large website, especially for thoes pages who contain AJAX requests. In that case, one reload of a page may trigger dozens of http request, each of them goes to a different URL. The new debugger engine will catch all connections from apache server. Users can debugger all of them without missing anyone.

### Break only at breakpoints

    let g:debuggerBreakAtEntry = 0

    The setting will cause debugger engine to break only at breakpoints. Default value is 1, which means it works like before, the debugger engine breaks at entry.

### Other new commands

    Pg        => to print value of complex variables like $this->savings[3]
    Bl        => to list all breakpoints
    Bae       => set debuggerBreakAtEntry, for example, :Bae 0 will set g:debuggerBreakAtEntry=0, which causes debugger engine breaks only at breakpoints.

Existing commands --

    Bp        => toggle breakpoint on current line
    Up        => goto upper level of stack 
    Dn        => goto lower level of stack 
    ,pe       => evalute expression and display result. cursor is automatically move to watch window. type line and just press enter. 
In debuggin mode 
    <F1>      => resizing windows 
    <F2>      => step into 
    <F3>      => step over 
    <F4>      => step out 
    <F6>      => stop debugging 
    <F11>     => shows all variables 
    <F12>     => shows variable on current cursor 

### Windows Support

### Status line for debugger engine

    LISN      => means the debugger engine is listening.
    PENDn     => means there are n connections waiting for debugging.
    CONN      => means debug session has been established, and being debugged.
    CLSD      => means the debugger engine has stopped.


## Usage

### Install xdebug for php, and edit php.ini

    zend_extension=<path_to_xdebug.so>
    xdebug.remote_enable=1

### Edit your ~/.vimrc

    let g:debuggerPort = 6789
    let g:debuggerBreakAtEntry = 0

### Edit your apche configure file
In your VirtualHost section, set debugger port same as the one in your vimrc

    php_value xdebug.remote_port 6789

### Save debugger.py and debugger.vim to your ~/.vimr/plugin

### Open your php file, use :Bp to set breakpoints

### Now, press F5 to start debugger engine

### Back to your browser, add XDEBUG_SESSION_START=1 to your URL, for example, http://localhost/index.php?XDEBUG_SESSION_START=1. If you would like to debug from CLI, start your php script like 

    php -dxdebug.remote_autostart=1 -dxdebug.remote_port 6789 test.php
