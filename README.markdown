This is a plugin to enable php debug in VIM with Xdebug, which is based on
http://www.vim.org/scripts/script.php?script_id=1152
http://www.vim.org/scripts/script.php?script_id=1929

My enhancements are --

* Non blocking debugger engine.
So that VIM users do not need to wait for connection from apache server. No timeout things, users press F5 to start debugger engine, and uses his/her VIM normally. Debug engine won't stop users to interact with VIM. Users can press F6 to stop debugger engine anytime.

* Catch all connections from apache server.
This is very important for a large website, especially for thoes pages who contain AJAX requests. In that case, one reload of a page may trigger dozens of http request, each of them goes to a different URL. The new debugger engine will catch all connections from apache server. Users can debugger all of them without missing anyone.

* Break only at breakpoints

    let g:debuggerBreakAtEntry = 0

The setting will cause debugger engine to break only at breakpoints. Default value is 1, which means it works like before, the debugger engine breaks at entry.

* Other new commands

    :Pg         => to print value of complex variables like $this->savings[3]
    :Bl         => to list all breakpoints
    :Bae        => set debuggerBreakAtEntry, for example, :Bae 0 will set g:debuggerBreakAtEntry=0, which causes debugger engine breaks only at breakpoints.

* Windows Support
