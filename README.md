# Metagov

Metagov is intended to help developers and users quickly prototype and deploy governance modules and governance structures within any online community (across games, blockchains, and social networks). It is being developed by the [Metagovernance Project](www.metagov.org), a nonprofit research group focused on the governance of virtual worlds.

Currently, this repo is mostly a placeholder for documentation related to speccing out early prototypes of the toolset. It is intended to facilitate and serve as a site for collaboration with developers interested in contributing to the project. 

## Development roadmap
To get a broad sense of what is going on, take a look at the diagram below.

![The life cycle of governance](https://github.com/thelastjosh/metagov-prototype/blob/master/Stages%20of%20governance.jpg "Life cycle of governance")

Roughly, we are prototyping **the agreement engine**, which will be used to draft both (dumb and smart) contracts and organizational charters / constitutions. The final output has to port into a range of social platforms, from blockchains to social networks to certain online games, but currently we can ignore questions of portability and just think about the basic logic and user experience.

Once you understand the general idea of the tool (feel free to ask questions!), use the roadmap below to figure out what needs doing. Note that the roadmap is constantly evolving (after all, this is a research project!). The most up-to-date version of the roadmap can be found [here](https://docs.google.com/document/d/1QDq89dogQb-K2jdDV5QL4Lqi8yehE3aiXzwVG8D24rY/edit#).

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

## UI research
1. [Agreement mockups](https://drive.google.com/open?id=1jCyOkpSSgoLUBBUsW0q9ediwtW6-OT0a)
2. [Constitution menu mockups](https://drive.google.com/file/d/1yqeXb8rGE3HqYbkAF-31_v5osRDKSdFy/view?usp=sharing) (developed by Klang Games)
