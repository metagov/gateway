# Metagov

Help us build a governance layer for the Web!

The Metagov toolset is intended to help developers and users quickly prototype and deploy governance modules and governance structures within an online community. It is being developed by the [Metagovernance Project](www.metagov.org), a nonprofit research group focused on the governance of virtual worlds.

Currently, this repo is mostly a placeholder for documentation related to speccing out early prototypes of the toolset. It is intended to facilitate and serve as a site for collaboration with developers interested in contributing to the project. 

To get a sense of what is going on, take a look at the diagram below.

![The life cycle of governance](https://github.com/thelastjosh/metagov-prototype/blob/master/Stages%20of%20governance.jpg "Life cycle of governance")

Roughly, we are implementing the agreement engine, which doubles as a constitution-maker.

## Development roadmap
Use the roadmap to figure out what needs doing. Note that the roadmap is constantly evolving (after all, this is a research project!). The most update to date version of the roadmap can be found [here](https://docs.google.com/document/d/1QDq89dogQb-K2jdDV5QL4Lqi8yehE3aiXzwVG8D24rY/edit#).

### Metagov v0.1: spreadsheet for governance designers and metagovernance designers
A wiki-style Google spreadsheet. See metagov.org/govlist.

- AU, I have direct access to Google spreadsheet via link.
- AU, the first thing I see is a welcoming, visually-pleasing set of instructions on how to use the spreadsheet (+ norms, + WhatsApp group link).
- AU, I can add new governance structures and new governance incidents to the table.
- AU, I cannot modify certain rows and columns of the sheet (e.g. the top row).
- Some of the values in each new governance structure or governance incident (e.g. “type” or “level”) come from a drop-down menu (or must be validated).
- Governance modules are a specific kind of governance structure.
- AU, any module I add to the governance structures spreadsheet automatically creates a new entry in the “Module” table (and vice versa).
- AU, I can specify the dependencies of a governance module.
- AU, I can specify the functions of a governance module, and their input and output types.
- AU, I can specify the parameters of a governance module.

### Metagov v0.2, extended prototype for governance fantasists
A constitution creator web app, built in Python + jQuery, which connects to the Google spreadsheet.

- Connector to Google spreadsheet, Python + jQuery web app.
- AU, I can specify an “end-to-end” governance system using a list of governance structures, especially governance modules.
- AU, I can reference any governance module (and governance system) against a list of “relevant” governance incidents.
- AU, I can “connect” modules along shared inputs/outputs.
- Modules have icons.
- All modules have tooltips (imported from sheets).
- AU, I can add tooltips to modules via the Google spreadsheet.
- As a dev, I can define a custom view of any given module.
- As a dev, I can add sliders, drop-down menus, text boxes, and code boxes.
- AU, I can access a flat view of my governance system as a list of rules.
- AU, I can print my governance system as an HTML page.
- AU, I can export and save my governance system locally as an XML document.
- AU, I can load saved governance systems.

## UI research
1. [Agreement mockups](https://drive.google.com/open?id=1jCyOkpSSgoLUBBUsW0q9ediwtW6-OT0a)
2. [Constitution menu mockups](https://drive.google.com/file/d/1yqeXb8rGE3HqYbkAF-31_v5osRDKSdFy/view?usp=sharing) (developed by Klang Games)
3. [Govlist spreadsheet, for early prototypes](www.metagov.org/govlist)

## Research background
1. [Modular Politics](https://docs.google.com/document/d/1c4vp4HQFYHNsFzm4rNo2uh4fU8Gonfu9nJOLpasel5I/edit)
