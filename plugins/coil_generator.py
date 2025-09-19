import pcbnew
import FootprintWizardBase
import math
import json
import os

from .PCBTraceComponent import *


class CoilGeneratorID2L(PCBTraceComponent):
    center_x = 0
    center_y = 0

    json_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "CoilGeneratorID2L.json"
    )

    GetName = lambda self: "Coil Generator from ID"
    GetDescription = lambda self: "Generates a coil around a circular aperture."
    GetValue = lambda self: "Coil based on ID"

    def GenerateParameterList(self):
        # Set some reasonable default values for the parameters
        defaults = {
            "Coil specs": {
                "Total Turns": 15,
                "First Layer": "F_Cu",
                "Second Layer": "B_Cu",
                "Direction": True,
            },
            "Install Info": {
                "Inside Diameter, Radius": 30000000,
                "Inner Ring gap": 500000,
            },
            "Fab Specs": {
                "Trace Width": 200000,
                "Trace Spacing": 200000,
                "Via Drill": 300000,
                "Via Annular Ring": 150000,
                "Pad Drill": 500000,
                "Pad Annular Ring": 200000,
                "Copper Thickness (Oz.Cu.)": 1,
            },
        }

        # If this has been run before, load the previous values
        if os.path.exists(self.json_file):
            with open(self.json_file, "r") as f:
                defaults = json.load(f)

        # Info about the coil itself.
        self.AddParam(
            "Coil specs",
            "Total Turns",
            self.uInteger,
            defaults["Coil specs"]["Total Turns"],
            min_value=1,
        )
        self.AddParam(
            "Coil specs",
            "First Layer",
            self.uString,
            defaults["Coil specs"]["First Layer"],
            hint="Layer name.  Uses '_' instead of '.'",
        )
        self.AddParam(
            "Coil specs",
            "Second Layer",
            self.uString,
            defaults["Coil specs"]["Second Layer"],
            hint="Layer name.  Uses '_' instead of '.'",
        )
        self.AddParam(
            "Coil specs",
            "Direction",
            self.uBool,
            defaults["Coil specs"]["Direction"],
            hint="Set to True for clockwise, False for counter-clockwise",
        )

        # Information about where this footprint needs to fit into.
        self.AddParam(
            "Install Info",
            "Inside Diameter, Radius",
            self.uMM,
            pcbnew.ToMM(30000000),
            # pcbnew.ToMM(defaults["Install Info"]["Inside Diameter, Radius"]),
        )
        self.AddParam(
            "Install Info",
            "Inner Ring gap",
            self.uMM,
            pcbnew.ToMM(defaults["Install Info"]["Inner Ring gap"]),
            hint="Gap between the innermost loop of this coil and the aperture",
        )

        # Info about the fabrication capabilities
        self.AddParam(
            "Fab Specs",
            "Trace Width",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Trace Width"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Trace Spacing",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Trace Spacing"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Via Drill",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Via Drill"]),
            min_value=0,
            hint="Diameter",
        )
        self.AddParam(
            "Fab Specs",
            "Via Annular Ring",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Via Annular Ring"]),
            min_value=0,
            hint="Radius",
        )
        self.AddParam(
            "Fab Specs",
            "Pad Drill",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Pad Drill"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Pad Annular Ring",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Pad Annular Ring"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Copper Thickness (Oz.Cu.)",
            self.uFloat,
            defaults["Fab Specs"]["Copper Thickness (Oz.Cu.)"],
            min_value=0.01,
        )

    def CheckParameters(self):
        self.aperture_r = self.parameters["Install Info"]["Inside Diameter, Radius"]
        self.aperture_gap = self.parameters["Install Info"]["Inner Ring gap"]

        self.trace_width = self.parameters["Fab Specs"]["Trace Width"]
        self.trace_space = self.parameters["Fab Specs"]["Trace Spacing"]
        self.via_hole = self.parameters["Fab Specs"]["Via Drill"]
        self.via_ann_ring = self.parameters["Fab Specs"]["Via Annular Ring"]
        self.pad_hole = self.parameters["Fab Specs"]["Pad Drill"]
        self.pad_ann_ring = self.parameters["Fab Specs"]["Pad Annular Ring"]
        self.copper_thickness = self.parameters["Fab Specs"][
            "Copper Thickness (Oz.Cu.)"
        ]

        self.turns = self.parameters["Coil specs"]["Total Turns"]
        self.first_layer = getattr(pcbnew, self.parameters["Coil specs"]["First Layer"])
        self.second_layer = getattr(
            pcbnew, self.parameters["Coil specs"]["Second Layer"]
        )
        self.clockwise_bool = self.parameters["Coil specs"]["Direction"]

        with open(self.json_file, "w") as f:
            json.dump(self.parameters, f, indent=4)

    def BuildThisFootprint(self):
        self.trace_length = 0
        self.vias = 0

        self.odd_loops = (self.turns % 2) == 1
        self.odd_loops_multiplier = -1 if self.odd_loops else 1
        self.cw_multiplier = 1 if self.clockwise_bool else -1

        """Draw the outline circle as reference."""
        self.draw.SetLayer(pcbnew.User_1)
        self.draw.Circle(self.center_x, self.center_y, self.aperture_r)

        self.draw.SetLayer(pcbnew.F_Fab)
        self.draw.Value(0, 0, pcbnew.FromMM(1))
        self.draw.SetLayer(pcbnew.F_SilkS)
        self.draw.Reference(0, 0, pcbnew.FromMM(1))

        """ Calculate several of the internal variables needed. """
        via_d = self.via_ann_ring * 2 + self.via_hole
        pad_d = self.pad_ann_ring * 2 + self.pad_hole

        self.draw.SetLineThickness(self.trace_width)

        # Set the arc origins
        del_o_1 = max(via_d, self.trace_width) / 2 - self.trace_width / 2
        del_o_2 = max(via_d, self.trace_width) / 2 + self.trace_space / 2

        """
        Draw the starting via between the front and back layers
        """
        pad_number = 3
        pos = pcbnew.VECTOR2I(
            int(self.aperture_r + self.aperture_gap + max(via_d, self.trace_width) / 2)
            * self.odd_loops_multiplier,
            0,
        )
        self.PlacePad(pad_number, pos, via_d, self.via_hole, via=True)

        """
        Draw the coils themselves
        """
        # Draw the first winding
        arc_center_x = self.center_x + del_o_1 / 2 * self.odd_loops_multiplier
        arc_start_x = (
            self.aperture_r + self.aperture_gap + max(via_d, self.trace_width) / 2
        ) * self.odd_loops_multiplier
        degrees = 180
        self.DrawArcsYSym2Layer(
            self.first_layer, self.second_layer, arc_center_x, arc_start_x, degrees
        )

        for ii in range(1, self.turns, 2):
            arc_center_x = self.center_x + del_o_2 * self.odd_loops_multiplier
            arc_start_x = (
                -(
                    self.aperture_r
                    + self.aperture_gap
                    + (ii / 2) * (self.trace_width + self.trace_space)
                    - 0.5 * self.trace_space
                )
                * self.odd_loops_multiplier
            )
            degrees = 180
            self.DrawArcsYSym2Layer(
                self.first_layer, self.second_layer, arc_center_x, arc_start_x, degrees
            )

        for ii in range(2, self.turns, 2):
            arc_center_x = (
                self.center_x
                + del_o_1 * (0.5 if ii == 0 else 1) * self.odd_loops_multiplier
            )
            arc_start_x = (
                self.aperture_r
                + self.aperture_gap
                + max(via_d, self.trace_width)
                + (ii / 2) * (self.trace_width + self.trace_space)
                - 0.5 * self.trace_width
            ) * self.odd_loops_multiplier
            degrees = 180
            self.DrawArcsYSym2Layer(
                self.first_layer, self.second_layer, arc_center_x, arc_start_x, degrees
            )

        """
        Finish the inductor with nice tails and pads.
        """
        arc_start_x = (
            self.center_x
            + self.aperture_r
            + self.aperture_gap
            + (self.trace_width if self.odd_loops else max(via_d, self.trace_width))
            + (self.turns // 2) * (self.trace_space + self.trace_width)
            - self.trace_width / 2
        )
        arc_center_x = arc_start_x + max(via_d, self.trace_width) * 2
        degrees = -90
        self.DrawArcsYSym2Layer(
            self.first_layer, self.second_layer, arc_center_x, arc_start_x, degrees
        )

        pad_number = 1
        pos = pcbnew.VECTOR2I(
            int(arc_center_x),
            -int(max(via_d, self.trace_width) * 2 * self.cw_multiplier),
        )
        self.PlacePad(pad_number, pos, pad_d, self.pad_hole)

        pad_number = 2
        pos = pcbnew.VECTOR2I(
            int(arc_center_x),
            int(max(via_d, self.trace_width)) * 2 * self.cw_multiplier,
        )
        self.PlacePad(pad_number, pos, pad_d, self.pad_hole)

        """
        Add Net Tie Group to the footprint. This allows the DRC to understand
        that the shorting traces are OK for this component
        """
        self.GenerateNetTiePadGroup()

        """
        Capture the parameters in the Fab layer
        """
        fab_text_s = (
            f"Coil Generator from ID, 2 Layers\n"
            f'Direction: {"CW" if self.clockwise_bool else "CCW"}\n'
            f"Inner Radius: {self.aperture_r/1e6}\n"
            f"Inner Ring Gap: {self.aperture_gap/1e6}\n"
            f"Turns: {self.turns}\n"
            f'Layers (Start->Finish): {self.parameters["Coil specs"]["First Layer"]}->{self.parameters["Coil specs"]["Second Layer"]}\n'
            f"Trace Width/space: {self.trace_width/1e6}/{self.trace_space/1e6}\n"
            f"Via Drill/annular ring: {self.via_hole/1e6}/{self.via_ann_ring/1e6}\n"
            f"Pad Drill/annular ring: {self.pad_hole/1e6}/{self.pad_ann_ring/1e6}\n"
        )
        self.DrawText(fab_text_s, pcbnew.User_2)

        """
        Capture the basic parameters in the Silk layer
        """
        basic_fab_text_s = (
            f"Turns: {self.turns}\n"
            f"R(@25C & {self.copper_thickness:.1f} Oz Cu): {self.GetResistance():.4f} Ohms\n"
        )
        self.DrawText(basic_fab_text_s, pcbnew.F_SilkS)


class CoilGenerator1L1T(PCBTraceComponent):
    center_x = 0
    center_y = 0

    json_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "CoilGenerator1L1T.json"
    )

    GetName = lambda self: "Coil Generator, single layer, 1 turn"
    GetDescription = lambda self: "Generates a single turn loop at a circular aperture."
    GetValue = lambda self: "Single coil, single layer"

    def GenerateParameterList(self):

        # Set some reasonable default values for the parameters
        defaults = {
            "Coil specs": {"Stub Length": 5000000, "Layer": "F_Cu", "Direction": True},
            "Install Info": {"Radius": 30000000},
            "Fab Specs": {
                "Trace Width": 200000,
                "Trace Spacing": 200000,
                "Pad Drill": 500000,
                "Pad Annular Ring": 200000,
            },
        }

        # If this has been run before, load the previous values
        if os.path.exists(self.json_file):
            with open(self.json_file, "r") as f:
                defaults = json.load(f)

        # Info about the coil itself.
        self.AddParam(
            "Coil specs",
            "Stub Length",
            self.uMM,
            pcbnew.ToMM(defaults["Coil specs"]["Stub Length"]),
            min_value=0,
        )
        self.AddParam(
            "Coil specs",
            "Layer",
            self.uString,
            defaults["Coil specs"]["Layer"],
            hint="Layer name.  Uses '_' instead of '.'",
        )
        self.AddParam(
            "Coil specs",
            "Direction",
            self.uBool,
            defaults["Coil specs"]["Direction"],
            hint="Set to True for clockwise, False for counter-clockwise",
        )

        # Information about where this footprint needs to fit into.
        self.AddParam(
            "Install Info",
            "Radius",
            self.uMM,
            pcbnew.ToMM(defaults["Install Info"]["Radius"]),
        )

        # Info about the fabrication capabilities
        self.AddParam(
            "Fab Specs",
            "Trace Width",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Trace Width"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Trace Spacing",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Trace Width"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Pad Drill",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Pad Drill"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Pad Annular Ring",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Pad Annular Ring"]),
            min_value=0,
        )

    def CheckParameters(self):
        self.radius = self.parameters["Install Info"]["Radius"]

        self.trace_width = self.parameters["Fab Specs"]["Trace Width"]
        self.trace_space = self.parameters["Fab Specs"]["Trace Spacing"]
        self.pad_hole = self.parameters["Fab Specs"]["Pad Drill"]
        self.pad_ann_ring = self.parameters["Fab Specs"]["Pad Annular Ring"]

        self.layer = getattr(pcbnew, self.parameters["Coil specs"]["Layer"])
        self.clockwise_bool = self.parameters["Coil specs"]["Direction"]
        self.stub_length = self.parameters["Coil specs"]["Stub Length"]

        with open(self.json_file, "w") as f:
            json.dump(self.parameters, f, indent=4)

    def BuildThisFootprint(self):
        self.cw_multiplier = 1 if self.clockwise_bool else -1

        """ Calculate several of the internal variables needed. """
        pad_d = self.pad_ann_ring * 2 + self.pad_hole
        radius1 = self.radius + self.trace_width / 2
        radius2 = self.trace_width

        theta2 = math.acos(
            (self.trace_space + max(pad_d, self.trace_width) / 2 + radius2)
            / (radius1 + radius2)
        )
        theta1 = math.pi / 2 - theta2

        self.draw.SetLayer(self.layer)
        self.draw.SetLineThickness(self.trace_width)

        """ Draw the main arc """
        arc_start_x = self.center_x + radius1 * math.cos(theta1)
        arc_start_y = self.center_y - radius1 * math.sin(theta1)
        self.draw.Arc(
            self.center_x,
            self.center_y,
            arc_start_x,
            arc_start_y,
            pcbnew.EDA_ANGLE(
                -2 * (math.pi - theta1) * self.cw_multiplier, pcbnew.RADIANS_T
            ),
        )

        """ Draw the stubs """
        arc_center_x = self.center_x + (radius1 + radius2) * math.cos(theta1)
        arc_center_y = self.center_y - (radius1 + radius2) * math.sin(theta1)
        self.draw.Arc(
            arc_center_x,
            arc_center_y,
            arc_start_x,
            arc_start_y,
            pcbnew.EDA_ANGLE(-theta2 * self.cw_multiplier, pcbnew.RADIANS_T),
        )
        self.draw.Arc(
            arc_center_x,
            -arc_center_y,
            arc_start_x,
            -arc_start_y,
            pcbnew.EDA_ANGLE(theta2 * self.cw_multiplier, pcbnew.RADIANS_T),
        )

        self.draw.Line(
            arc_center_x,
            max(pad_d, self.trace_width) / 2 + self.trace_space,
            arc_center_x + self.stub_length,
            max(pad_d, self.trace_width) / 2 + self.trace_space,
        )
        self.draw.Line(
            arc_center_x,
            -max(pad_d, self.trace_width) / 2 - self.trace_space,
            arc_center_x + self.stub_length,
            -max(pad_d, self.trace_width) / 2 - self.trace_space,
        )

        pad_number = 1
        pos = pcbnew.VECTOR2I(
            int(arc_center_x + self.stub_length),
            -int(max(pad_d, self.trace_width) / 2 + self.trace_space)
            * self.cw_multiplier,
        )
        self.PlacePad(pad_number, pos, pad_d, self.pad_hole)

        pad_number = 2
        pos = pcbnew.VECTOR2I(
            int(arc_center_x + self.stub_length),
            int(max(pad_d, self.trace_width) / 2 + self.trace_space)
            * self.cw_multiplier,
        )
        self.PlacePad(pad_number, pos, pad_d, self.pad_hole)

        """
        Add Net Tie Group to the footprint. This allows the DRC to understand
        that the shorting traces are OK for this component
        """
        self.GenerateNetTiePadGroup()

        """
        Capture the parameters in the Fab layer
        """
        fab_text_s = (
            f"Coil Generator, Single Layer, 1 Turn\n"
            f'Direction {"CCW" if self.clockwise_bool else "CW"}\n'
            f"Diameter: {self.radius/1e6}\n"
            f'Layer: {self.parameters["Coil specs"]["Layer"]}\n'
            f"Trace Width/space: {self.trace_width/1e6}/{self.trace_space/1e6}\n"
            f"Pad Drill/annular ring: {self.pad_hole/1e6}/{self.pad_ann_ring/1e6}\n"
            f"Stub Length: {self.stub_length/1e6}"
        )

        self.DrawText(fab_text_s, pcbnew.User_2)

class RectangleCoilGenerator(PCBTraceComponent):
    center_x = 0
    center_y = 0

    json_file = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "RectangleCoilGenerator.json"
    )

    GetName = lambda self: "Coil Generator Rectangle"
    GetDescription = lambda self: "Generates a rectangular-shaped coil."
    GetValue = lambda self: "Rectangle Coil"

    def GenerateParameterList(self):
        # Set default values for rectangular coil parameters
        defaults = {
            "Coil specs": {
                "Total Turns": 10,
                "First Layer": "F_Cu",
                "Second Layer": "B_Cu",
                "Width": 30000000,
                "Height": 20000000,
                "Stub Length": 1000000,
                "Direction": True,
                "Rounding Radius": 1000000
            },
            "Fab Specs": {
                "Trace Width": 200000,
                "Trace Spacing": 200000,
                "Via Drill": 300000,
                "Via Annular Ring": 150000,
                "Pad Drill": 500000,
                "Pad Annular Ring": 200000,
                "Copper Thickness (Oz.Cu.)": 1,
            },
        }

        # Load previous values if available
        if os.path.exists(self.json_file):
            with open(self.json_file, "r") as f:
                defaults = json.load(f)

        # Add parameters
        self.AddParam(
            "Coil specs",
            "Total Turns",
            self.uInteger,
            defaults["Coil specs"]["Total Turns"],
            min_value=1,
        )
        self.AddParam(
            "Coil specs",
            "First Layer",
            self.uString,
            defaults["Coil specs"]["First Layer"],
            hint="Layer name. Uses '_' instead of '.'",
        )
        self.AddParam(
            "Coil specs",
            "Second Layer",
            self.uString,
            defaults["Coil specs"]["Second Layer"],
            hint="Layer name. Uses '_' instead of '.'",
        )

        self.AddParam(
            "Coil specs",
            "Width",
            self.uMM,
            pcbnew.ToMM(defaults["Coil specs"]["Width"]),
        )
        self.AddParam(
            "Coil specs",
            "Height",
            self.uMM,
            pcbnew.ToMM(defaults["Coil specs"]["Height"]),
        )
        self.AddParam(
            "Coil specs",
            "Stub Length",
            self.uMM,
            pcbnew.ToMM(defaults["Coil specs"]["Stub Length"]),
            hint="Length of stubs to pads and via",
        )
        self.AddParam(
            "Coil specs",
            "Direction",
            self.uBool,
            defaults["Coil specs"]["Direction"],
            hint="Set to True for clockwise, False for counter-clockwise",
        )

        self.AddParam(
            "Coil specs",
            "Rounding Radius",
            self.uMM,
            pcbnew.ToMM(defaults["Coil specs"]["Rounding Radius"]),
            hint="Set to 0 for no rounding",
        )

        self.AddParam(
            "Fab Specs",
            "Trace Width",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Trace Width"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Trace Spacing",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Trace Spacing"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Via Drill",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Via Drill"]),
            min_value=0,
            hint="Diameter",
        )
        self.AddParam(
            "Fab Specs",
            "Via Annular Ring",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Via Annular Ring"]),
            min_value=0,
            hint="Radius",
        )
        self.AddParam(
            "Fab Specs",
            "Pad Drill",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Pad Drill"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Pad Annular Ring",
            self.uMM,
            pcbnew.ToMM(defaults["Fab Specs"]["Pad Annular Ring"]),
            min_value=0,
        )
        self.AddParam(
            "Fab Specs",
            "Copper Thickness (Oz.Cu.)",
            self.uFloat,
            defaults["Fab Specs"]["Copper Thickness (Oz.Cu.)"],
            min_value=0.01,
        )

    def CheckParameters(self):
        self.turns = self.parameters["Coil specs"]["Total Turns"]
        self.first_layer = getattr(pcbnew, self.parameters["Coil specs"]["First Layer"])
        self.second_layer = getattr(pcbnew, self.parameters["Coil specs"]["Second Layer"])

        self.width = self.parameters["Coil specs"]["Width"]
        self.height = self.parameters["Coil specs"]["Height"]
        self.stub_len = self.parameters["Coil specs"]["Stub Length"]
        self.clockwise_bool = self.parameters["Coil specs"]["Direction"]
        self.rounding_radius = self.parameters["Coil specs"]["Rounding Radius"]

        self.trace_width = self.parameters["Fab Specs"]["Trace Width"]
        self.trace_space = self.parameters["Fab Specs"]["Trace Spacing"]
        self.via_hole = self.parameters["Fab Specs"]["Via Drill"]
        self.via_ann_ring = self.parameters["Fab Specs"]["Via Annular Ring"]
        self.pad_hole = self.parameters["Fab Specs"]["Pad Drill"]
        self.pad_ann_ring = self.parameters["Fab Specs"]["Pad Annular Ring"]
        self.copper_thickness = self.parameters["Fab Specs"]["Copper Thickness (Oz.Cu.)"]

        with open(self.json_file, "w") as f:
            json.dump(self.parameters, f, indent=4)

    def BuildThisFootprint(self):
        left, half_width, half_height, curr_radius = 0, 0, 0, 0
        kDegrees = 90

        self.draw.SetLineThickness(self.trace_width)
        cw_multiplier = 1 if self.clockwise_bool else -1

        def CalcStartPoint():
            nonlocal half_width, half_height, curr_radius, left
            half_width = self.width / 2
            half_height = self.height / 2
            curr_radius = self.rounding_radius
            left = self.center_x - half_width

        # ==== Draw the first winding ====
        self.draw.SetLayer(self.first_layer)
        CalcStartPoint()
        for turn in range(1, self.turns, 2):
            top = self.center_y - half_height * cw_multiplier
            right = self.center_x + half_width
            bottom = self.center_y + half_height * cw_multiplier

            # Left center to left top
            y_start = self.center_y
            y_end = top + curr_radius * cw_multiplier
            self.draw.Line(left, y_start, left, y_end)

            # Arc top left
            if(curr_radius > 0):
                center_x = left + curr_radius
                center_y = top + curr_radius * cw_multiplier
                self.draw.Arc(center_x, center_y, left, center_y, pcbnew.EDA_ANGLE(kDegrees* cw_multiplier, pcbnew.DEGREES_T))

            # Left top to right top
            x_start = left + curr_radius
            x_end = right - curr_radius
            self.draw.Line(x_start, top, x_end, top)

            # Arc top right
            if(curr_radius > 0):
                center_x = right - curr_radius
                center_y = top + curr_radius * cw_multiplier
                self.draw.Arc(center_x, center_y, center_x, top, pcbnew.EDA_ANGLE(kDegrees* cw_multiplier, pcbnew.DEGREES_T))

            # Right top to right bottom
            y_start = top + curr_radius * cw_multiplier
            y_end = bottom - curr_radius * cw_multiplier
            self.draw.Line(right, y_start, right, y_end)

            # Arc bottom right
            if(curr_radius > 0):
                center_x = right - curr_radius
                center_y = bottom - curr_radius * cw_multiplier
                self.draw.Arc(center_x, center_y, right, center_y, pcbnew.EDA_ANGLE(kDegrees* cw_multiplier, pcbnew.DEGREES_T))

            # Right bottom to left bottom
            half_width += self.trace_width + self.trace_space
            left = self.center_x - half_width
            x_start = right - curr_radius
            x_end = left + curr_radius
            self.draw.Line(x_start, bottom, x_end, bottom)

            # Arc bottom left
            if(curr_radius > 0):
                center_x = left + curr_radius
                center_y = bottom - curr_radius * cw_multiplier
                self.draw.Arc(center_x, center_y, center_x, bottom, pcbnew.EDA_ANGLE(kDegrees* cw_multiplier, pcbnew.DEGREES_T))

            # Left bottom to left center
            y_start = bottom - curr_radius * cw_multiplier
            y_end = self.center_y
            self.draw.Line(left, y_start, left, y_end)

            # Update dimensions for next turn
            half_height += self.trace_width + self.trace_space
            if(curr_radius > 0):
                curr_radius += self.trace_width + self.trace_space

        # ==== Draw the second winding ====
        # self.draw.SetLayer(self.second_layer)
        # CalcStartPoint()


        # ==== Add stubs and pads ====
        pad_d = self.pad_ann_ring * 2 + self.pad_hole # Common Pads params
        y = self.center_y
        # Stub 1
        x_start = self.center_x - self.width / 2 - (self.trace_width + self.trace_space) * self.turns // 2
        x_end = x_start - self.stub_len
        self.draw.SetLayer(self.first_layer)
        self.draw.Line(x_start, y, x_end, y)
        # Add pad
        self.PlacePad(1, pcbnew.VECTOR2I(int(x_end), int(y)), pad_d, self.pad_hole)

        # Stubs to via
        y = self.center_y
        x_start = self.center_x - self.width / 2
        x_end = x_start + self.stub_len
        self.draw.SetLayer(self.first_layer)
        self.draw.Line(x_start, y, x_end, y)
        self.draw.SetLayer(self.second_layer)
        self.draw.Line(x_start, y, x_end, y)
        # Add via
        self.PlacePad(3, pcbnew.VECTOR2I(int(x_end), int(y)), pad_d, self.pad_hole)
