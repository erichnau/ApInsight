---
title: 'ApInsight: Interactive analysis and visualization of three-dimensional ground-penetrating radar data'
tags:
  - Python
  - archaeology
  - ground-penetrating radar
  - geophysical prospection
  - visualization
  - research software
authors:
  - name: Erich Nau
    orcid: 0000-0002-1573-3544
    affiliation: 1
    corresponding: true
  - name: Markus Angermann
    affiliation: 2
affiliations:
  - name: Norwegian Institute for Cultural Heritage Research (NIKU), Norway
    index: 1
  - name: Angermann IT-Services GmbH, Vienna, Austria
    index: 2
date: 6 October 2026
bibliography: paper.bib
---

# Summary

Ground-penetrating radar (GPR) is widely used in archaeological prospection to map buried structures without excavation. Modern motorised multi-channel systems can survey several hectares per day at high spatial resolution, producing dense three-dimensional datasets containing information about the horizontal extent and vertical geometry of subsurface reflections [@trinks2018]. Archaeological interpretation often relies on horizontal time- or depth-slice images exported to geographic information systems (GIS). While this makes survey results accessible, vertical relationships within the processed volume are more difficult to investigate.

ApInsight is an open-source Python application developed to bridge this gap between specialist GPR processing and archaeological interpretation. It works with already processed, georeferenced three-dimensional GPR volumes. Users can explore horizontal depth slices and extract arbitrary vertical sections along lines chosen according to archaeological questions. The linked views, optional topographic correction, project storage, and GIS exchange allow the same dataset to be revisited as interpretation develops.

ApInsight was developed primarily for archaeological surveys processed with ApRadar and currently supports its `.fld` volume format [@apinsight2024]. Its main purpose is to give archaeological interpreters access to more of the processed three-dimensional information without requiring them to return to the original processing environment.

# Statement of need

Motorised multi-channel systems have substantially increased the coverage and spatial sampling of archaeological GPR surveys [@trinks2018]. However, improvements in acquisition and processing have not been matched by equivalent advances in archaeological interpretation [@verdonck2019]. Modern multichannel GPR systems can readily generate tens of gigabytes of raw data during a single day of fieldwork, making repeated handling of the complete raw dataset increasingly impractical for routine archaeological interpretation.

For small single-channel surveys, working within the original processing environment can be practical. Landscape-scale surveys introduce different requirements. Acquisition and initial processing require geophysical expertise, whereas archaeological assessment may take place much later, involve several researchers, or be repeated during excavation. Requiring every interpreter to handle the complete raw dataset and specialist processing software adds practical and, for commercial software, financial barriers. Raw measurements remain essential for archiving and reprocessing, but routine interpretation can instead use a prepared survey product.

Exporting georeferenced time- or depth-slices to GIS provides an accessible way to map anomalies and combine them with excavation plans, historical maps, and terrain models. However, reducing a three-dimensional GPR volume to a stack of horizontal images limits direct access to its vertical structure. Vertical sections can reveal relationships between reflections that are difficult to follow in plan, particularly where buildings overlap, buried surfaces survive, or archaeological structures occur within complex deposits. Interpretation also depends on relating these observations to archaeological context and other sources of evidence [@verdonck2019].

ApInsight retains the practical separation between geophysical processing and archaeological interpretation while keeping the processed volume available for further investigation. Processing specialists can prepare suitable datasets, and archaeologists can subsequently examine selected structures from different positions and orientations without repeating the processing chain.

# State of the field

Established GPR software already provides extensive processing, visualization, and interpretation capabilities. ReflexW supports two- and three-dimensional GPR processing and visualization, while GPR-SLICE is widely used in archaeological prospection and provides tools for processing, time- and depth-slice generation, and 2D/3D visualization [@reflexw; @gprslice]. ApRadar represents a more research-oriented processing environment developed specifically for large-scale archaeological prospection. It originated through work at ZAMG ArcheoProspections and the Ludwig Boltzmann Institute for Archaeological Prospection and Virtual Archaeology (LBI ArchPro), and this development is now continued at GeoSphere Austria [@wallner2022velm; @hinterleitner2023]. ApInsight does not aim to replace these processing environments. Instead, it uses the processed `.fld` volumes produced by ApRadar as the starting point for subsequent archaeological visualization and interpretation.

Open-source alternatives also overlap with parts of this workflow. GPRPy provides processing and visualization tools and can assemble processed profiles into three-dimensional data cubes [@plattner2020; @gprpycube]. RGPR supports importing, processing, gridding, time/depth slices, and three-dimensional exploration [@huber2018; @rgprdocs]. The more specialized `readgssi` provides reading and preprocessing of GSSI measurements [@readgssi2018]. Within QGIS, the Archaeological Geophysics Toolbox provides tools for resistivity, magnetic, and electromagnetic-induction data [@agt].

ApInsight therefore does not aim to replace existing GPR processing software or GIS environments, but to complement them by providing a lightweight, open-source interface for archaeological exploration of already processed 3D GPR volumes. This specific position between specialist GPR processing and GIS-based archaeological interpretation motivated its development as a separate application.

Its present dependence on `.fld` is a limitation. Additional importers could reuse the analysis tools, but would need to supply compatible coordinates, sampling, time/depth metadata, and no-data conventions alongside the numerical array.

# Software design

ApInsight separates the processed GPR dataset from the project used to explore it. JSON project files link volumes, depth-slice images, digital terrain models, and saved section geometries. Several datasets or processing variants can be included without duplicating their data, although the linked files must remain accessible when projects are shared. The overall workflow and data structure are summarized in Figure 1.

The Tkinter-based plan viewer acts as a simplified GIS interface: users can browse georeferenced depth slices, read coordinates, measure distances and areas, and draw section lines. These lines link the horizontal view to the corresponding vertical section, allowing observations in profile to be located directly in plan. Figure 2 shows the linked plan and section views for a burial mound at Melhus, where the mound survives beneath a quick-clay slide and is visible both in plan and in the extracted section.

FLD data are converted to NumPy arrays and associated with spatial and vertical coordinates through xarray. An optional compiled C++ converter accelerates decoding of large volumes. This avoids repeated decoding during subsequent use; the reduction from raw measurements to an interpretation product occurs during upstream processing rather than through NumPy conversion itself.

Processed GPR products commonly use amplitude-envelope values, derived using the Hilbert transform, to emphasize reflection strength in time- or depth-slices [@verdonck2019]. ApInsight also supports every-sample `.fld` volumes, retaining the samples of the processed traces rather than only interval-based slices. Envelope processing and vertical sampling are separate choices: an every-sample volume may contain signed amplitudes or envelope values, depending on its processing history.

For section extraction, the user defines two endpoints on a depth slice. ApInsight samples the line through the volume by linear interpolation, independently of the original acquisition direction. Sections can therefore cross a building, mound, or sequence of anomalies according to the question being investigated. Finer display sampling improves visual continuity but does not increase geophysical resolution.

Where a terrain model is available, elevation differences along the line are used to shift section columns vertically for topographic display. Section geometries can be saved or exchanged as Shapefiles, and section images exported as PNG files. Automated tests cover selected coordinate calculations, interpolation, topographic shifts, and project-file operations; GitHub Actions runs them with Python 3.12 and 3.14.

![Schematic workflow and data structure of ApInsight. Processed GPR products remain external files linked through a lightweight JSON project. The plan and section views provide linked access to the processed 3D volume, while section geometries and images can be exported for GIS, reporting, and other workflows.\label{fig:workflow}](figures/apinsight_workflow.png){width="100%"}

![Linked plan and section views in ApInsight, illustrated with a burial mound at Melhus preserved beneath a quick-clay slide. (a) The plan view shows the selected depth slice and the user-defined section line A–B across the mound. (b) The section view displays the corresponding vertical profile extracted through the processed 3D volume. Screenshot supplied by the author.\label{fig:gui}](figures/apinsight_gui_plan_section.png){width="100%"}

# Research impact statement

Development began as a private Python project in 2020 and expanded into **Schlitzi+** within the Vestfold Monitoring Project (VEMOP). The project required comparison of more than 100 repeated GPR surveys with environmental observations. Its public accounts describe project-based organization, arbitrary profiles, and individual-trace extraction, and identify generalization and documentation for wider archaeological use as the next development step [@vemop2021; @vemop2022]. Refactoring supported from 2023 led to the public release of ApInsight in 2024.

Schlitzi+ was also used in archaeological survey work outside the monitoring project. At Nergården, Bjarkøy, a profile through the southern part of a presumed boat workshop helped examine a reflective layer interpreted as a floor extending beneath a cultivation bank. The report explicitly identifies Schlitzi+ as the software used to produce the profile [@bjarkoy, p. 18, fig. 7]. This documents an application of the predecessor before release under the ApInsight name.

The survey of Myklebusthaugen provides a practical example of this division of work. GPR data were processed by the first author at NIKU, while Grethe Moéll Pedersen and Kristoffer Hillesland at the Archaeological Museum, University of Stavanger, used ApInsight for analysis, interpretation, and extraction of digital profiles [@hillesland2024myklebust, p. 19]. These profiles helped investigate the mound's layered construction and identify the trench excavated by Anders Lorange in 1874. Subsequent excavation by the University Museum of Bergen confirmed the layered construction and trench location, but also revealed deeper features that had not been recognized in the GPR data [@hillesland2024myklebust, pp. 21--27, 50--51].

Independent technical reuse is documented by @blochberger2025, who based an FLD-to-point-cloud conversion script on ApInsight for joint surface and subsurface visualization. Within NIKU, ApInsight sections supported investigation of former riverbanks at Mørstad [@niku2026morstad].

The anthology *Arkeologisk geofysikk i Norge* discusses ApInsight's place in Norwegian methodological development and illustrates its plan/profile approach [@nau2026history; @nau2026visualization]. Further work on QGIS integration, polyline sections, and assisted feature detection builds on the software but lies outside the standalone application described here.

# AI usage disclosure

ChatGPT (OpenAI) assisted literature and software searches, manuscript drafting and revision, documentation, and regression-test development. The original Schlitzi+/ApInsight concept and the first released core predate the use of generative AI in this work. Suggested changes were assessed through source checking, manual code inspection, and deterministic numerical tests run locally and in continuous integration. The authors reviewed the resulting software description, references, and manuscript and retain responsibility for their content.

# Acknowledgements

Development was supported by strategic research funding from the Norwegian Institute for Cultural Heritage Research (NIKU), through institutional basic funding administered by the Research Council of Norway. The predecessor software was developed within VEMOP, supported by the regional research fund Oslofjordfondet. GeoSphere Austria provided additional financial support. The authors thank Alois Hinterleitner for assistance with the ApRadar `.fld` format.
