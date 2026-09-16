import tkinter as tk
from tkinter import ttk, messagebox


class TopFrameToolsApPPD(ttk.Frame):
    """Toolbar dedicated to ApPPD; no velocity-model or file-navigation controls."""
    def __init__(self, master, viewer):
        super().__init__(master); self.viewer=viewer
        row=ttk.Frame(self);row.pack(fill='x')
        for label, command in [('Home',viewer.home),('Pan',viewer.pan),('Zoom',viewer.zoom),('Save image',viewer.save_image),('Export arrays',viewer.export_arrays),('Reset display',self.reset)]:
            ttk.Button(row,text=label,command=command).pack(side='left',padx=3,pady=3)
        self.late=tk.BooleanVar(value=False)
        self.height_radius=tk.StringVar(value='0.35')
        self.late_start=tk.StringVar(value='35');self.late_ramp=tk.StringVar(value='5');self.late_strength=tk.StringVar(value='0.5')
        self.agc=tk.BooleanVar(value=False); self.topo=tk.BooleanVar(value=False)
        self.window=tk.StringVar(value='50'); self.strength=tk.StringVar(value='1.0')
        self.floor=tk.StringVar(value='0.05'); self.clip=tk.StringVar(value='99')
        self.velocity=tk.StringVar(value='0.10'); self.offset=tk.StringVar(value='0')
        row=ttk.Frame(self);row.pack(fill='x')
        ttk.Checkbutton(row,text='RMS AGC',variable=self.agc).pack(side='left')
        for label,var in [('Window (samples)',self.window),('Strength 0–1',self.strength),('RMS floor',self.floor),('Clip percentile',self.clip)]:
            ttk.Label(row,text=label).pack(side='left',padx=3);ttk.Entry(row,textvariable=var,width=6).pack(side='left')
        row=ttk.Frame(self);row.pack(fill='x')
        ttk.Checkbutton(row,text='Source-height correction',variable=self.topo).pack(side='left')
        for label,var in [('Velocity (m/ns)',self.velocity),('Antenna above ground (m)',self.offset)]:
            ttk.Label(row,text=label).pack(side='left',padx=3);ttk.Entry(row,textvariable=var,width=7).pack(side='left')
        ttk.Label(row,text='Height smoothing σ (m)').pack(side='left')
        ttk.Entry(row,textvariable=self.height_radius,width=6).pack(side='left')
        row=ttk.Frame(self);row.pack(fill='x')
        ttk.Checkbutton(row,text='Late-time smoothing',variable=self.late).pack(side='left')
        for label,var in [('Start (ns)',self.late_start),('Ramp (ns)',self.late_ramp),('Strength 0–1',self.late_strength)]:
            ttk.Label(row,text=label).pack(side='left',padx=3);ttk.Entry(row,textvariable=var,width=6).pack(side='left')
        ttk.Button(row,text='Apply',command=self.apply).pack(side='left',padx=8)
        ttk.Label(self,text='Height mode assumes source z is in metres in a common vertical datum. AGC changes relative amplitudes.').pack(anchor='w',padx=4)

    def apply(self):
        try:
            settings=dict(late=self.late.get(),late_start=float(self.late_start.get()),late_ramp=float(self.late_ramp.get()),late_strength=float(self.late_strength.get()),height_radius=float(self.height_radius.get()),agc=self.agc.get(),window=int(self.window.get()),strength=float(self.strength.get()),floor_fraction=float(self.floor.get()),clip=float(self.clip.get()),topo=self.topo.get(),velocity=float(self.velocity.get()),antenna_offset=float(self.offset.get()))
            self.viewer.apply(settings)
        except (ValueError,OverflowError) as exc:
            messagebox.showerror('ApPPD display',str(exc),parent=self)

    def reset(self):
        self.late.set(False);self.agc.set(False);self.topo.set(False);self.clip.set('99');self.apply()
