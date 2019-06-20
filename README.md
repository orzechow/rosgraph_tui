# rosgraph_tui

*rosgraph_tui* is a [terminal user interface (TUI)](https://en.wikipedia.org/wiki/Text-based_user_interface) that 
allows you to explore and debug your ROS graph interactively.

It is meant as a substitute of [rqt_graph](https://wiki.ros.org/rqt_graph), 
which is very handy for small projects, but virtually unusable with huge graphs 
consisting of dozens or hundreds of nodes and topics.

To tackle this, *rosgraph_tui* lets you search topics or nodes quickly, analyze them 
and interactively navigate through the ROS graph.

*rosgraph_tui* is powered by the TUI library [urwid](https://github.com/urwid/urwid)
and [fuzzywuzzy](https://github.com/seatgeek/fuzzywuzzy) for fuzzy search.


## Installation

```bash
pip install rosgraph-tui
```

## Usage

Simply run `rosgraph_tui` from a sourced ROS workspace, search by typing and navigate with arrow keys.
