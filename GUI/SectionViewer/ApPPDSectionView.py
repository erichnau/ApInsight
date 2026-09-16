"""ApPPD viewer using SectionCanvas velocity-mode Matplotlib navigation."""
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from .SectionCanvas import SectionCanvas
from .TopFrameToolsApPPD import TopFrameToolsApPPD
from .ap_ppd_display_processing import agc_display, topographic_display, edges, smooth_heights, late_smoothing


class ApPPDCanvas(SectionCanvas):
    def __init__(self, master):
        super().__init__(master, section=None, temp_folder_path=None, mode='velocity')
        self.figure=Figure(figsize=(12,6),layout='constrained')
        self.ax=self.figure.add_subplot(111)
        self.canvas=FigureCanvasTkAgg(self.figure,master=self)
        self.canvas.get_tk_widget().pack(fill='both',expand=True)
        self.toolbar=NavigationToolbar2Tk(self.canvas,self,pack_toolbar=False)
        self.toolbar.update()
        self.image=None

    def render(self,data,x,y,clip,elevation=False,reset=False,heights=None):
        old=(self.ax.get_xlim(),self.ax.get_ylim()) if self.image is not None and not reset else None
        self.ax.clear()
        finite=abs(data[np.isfinite(data)]);lim=max(float(np.percentile(finite,clip)) if finite.size else 1.,1e-12)
        self.image=self.ax.pcolormesh(edges(x),edges(y),np.ma.masked_invalid(data),cmap='gray',vmin=-lim,vmax=lim,shading='flat',rasterized=True)
        self.ax.set_xlabel('Distance along polysection (m)')
        self.ax.set_ylabel('Elevation (m, source datum)' if elevation else 'Two-way time after header time zero (ns)')
        self.ax.set_xlim(edges(x)[0],edges(x)[-1])
        self.ax.set_ylim((edges(y)[-1],edges(y)[0]))
        if elevation and heights is not None:self.ax.plot(x,heights,color='tab:orange',lw=.8)
        if old:self.ax.set_xlim(old[0]);self.ax.set_ylim(old[1])
        else:self.toolbar.update();self.toolbar.push_current()
        self.canvas.draw_idle()


class ApPPDSectionView(tk.Toplevel):
    def __init__(self,master,sections,title='ApPPD polysection',image_frame=None,vertices=None):
        super().__init__(master);self.title(title);self.geometry('1250x750')
        self.original=np.array(sections['final_section'],dtype=float,copy=True)
        self.distance=np.asarray(sections['distance'],float)
        self.dt=float(sections['sample_interval_ns'])
        self.heights=np.asarray(sections.get('surface_elevation',np.full(len(self.distance),np.nan)),float)
        if self.original.ndim!=2 or self.original.shape[1]!=len(self.distance) or len(self.distance)<2 or not np.all(np.diff(self.distance)>0) or not np.isfinite(self.dt) or self.dt<=0:
            self.destroy();raise ValueError('Invalid section geometry or sample interval.')
        self.settings={};self.display=self.original.copy();self.y=np.arange(len(self.original))*self.dt
        self.tf=TopFrameToolsApPPD(self,self);self.tf.pack(side='top',fill='x')
        self.section_canvas=ApPPDCanvas(self);self.section_canvas.pack(fill='both',expand=True)
        self.status=tk.StringVar();ttk.Label(self,textvariable=self.status).pack(fill='x')
        self.section_canvas.canvas.mpl_connect('button_press_event',self.inspect)
        self.cursor=None;self.map_link=None
        self.tf.apply()
        if image_frame is not None and vertices is not None:
            from .ApPPDMapLink import ApPPDMapLink
            self.map_link=ApPPDMapLink(self,image_frame,vertices)
        self.protocol('WM_DELETE_WINDOW',self.destroy)

    def home(self):self.section_canvas.velo_home()
    def pan(self):self.section_canvas.velo_pan()
    def zoom(self):self.section_canvas.velo_zoom()
    def save_image(self):self.section_canvas.velo_save_image()

    def apply(self,settings):
        if not 0<settings['clip']<=100:raise ValueError('Clip percentile must be >0 and <=100.')
        data=self.original.copy();y=np.arange(len(data))*self.dt;heights=None
        if settings['agc']:data=agc_display(data,settings['window'],settings['strength'],settings['floor_fraction'])
        if settings['late']:data=late_smoothing(data,self.dt,settings['late_start'],settings['late_ramp'],settings['late_strength'])
        self.time_display=data.copy()
        self.smoothed_heights=smooth_heights(self.heights,self.distance,settings['height_radius'])
        if settings['topo']:data,y,heights=topographic_display(data,self.dt,self.smoothed_heights,settings['velocity'],settings['antenna_offset'])
        reset=not self.settings or any(settings[k]!=self.settings.get(k) for k in ('topo','velocity','antenna_offset','height_radius'))
        self.section_canvas.render(data,self.distance,y,settings['clip'],settings['topo'],reset,heights)
        self.cursor=None
        self.display=data;self.y=y;self.settings=settings.copy()
        self.status.set('Display updated from the unchanged processed section. Click to inspect a sample.')

    def inspect(self,event):
        if event.inaxes is not self.section_canvas.ax or self.section_canvas.toolbar.mode:return
        j=int(np.argmin(abs(self.distance-event.xdata)));i=int(np.argmin(abs(self.y-event.ydata)))
        self.status.set(f'Column {j} | distance {self.distance[j]:.3f} m | vertical {self.y[i]:.3f} | amplitude {self.display[i,j]:.6g} | source height {self.heights[j]:.3f} m')

    def export_arrays(self):
        from pathlib import Path
        from .ap_ppd_mala_export import export_mala_rd3
        kind=tk.StringVar(value='NumPy archive')
        path=filedialog.asksaveasfilename(parent=self,defaultextension='',typevariable=kind,
            filetypes=[('NumPy archive','*.npz'),('NumPy displayed array','*.npy'),('MALA RD3 + RAD','*.rd3')])
        if not path:return
        suffix=Path(path).suffix.lower()
        if not suffix:
            suffix={'NumPy archive':'.npz','NumPy displayed array':'.npy','MALA RD3 + RAD':'.rd3'}.get(kind.get(),'.npz')
            path+=suffix
        try:
            if suffix=='.npz':
                np.savez_compressed(path,processed_section=self.original,display_section=self.display,distance=self.distance,
                    vertical_coordinate=self.y,surface_elevation=self.heights,sample_interval_ns=self.dt,
                    smoothed_heights=self.smoothed_heights,time_domain_display=self.time_display,settings_json=json.dumps(self.settings))
            elif suffix=='.npy':np.save(path,self.display)
            elif suffix=='.rd3':
                companions=[str(Path(path).with_suffix('.rad')),path+'.metadata.npz']
                if any(Path(p).exists() for p in companions) and not messagebox.askyesno('Overwrite companion files?',
                        'The RAD/header or metadata file already exists. Replace the export set?',parent=self):return
                info=export_mala_rd3(path,self.time_display,self.distance,self.dt,self.smoothed_heights,self.settings)
                messagebox.showinfo('MALA export',
                    'Saved RD3 + RAD. Import as MALA RD3 in ReflexW.\n'
                    'Time-domain data exported before topographic placement.\n'
                    f'16-bit quantization; amplitude scale: {info["scale"]:.6g}.\n'
                    f'Short final interval omitted: {info["trimmed"]}.\n'
                    f'Check imported dt = {self.dt:.9g} ns.',parent=self)
            else:raise ValueError('Choose .npz, .npy or .rd3.')
        except (ValueError,OSError) as exc:messagebox.showerror('Export',str(exc),parent=self)

    def set_cursor(self,distance):
        ax=self.section_canvas.ax
        if self.cursor is None:self.cursor=ax.axvline(distance,color='cyan',lw=.8)
        else:self.cursor.set_xdata([distance,distance])
        self.section_canvas.canvas.draw_idle()

    def destroy(self):
        if getattr(self,'map_link',None) is not None:
            try:self.map_link.close()
            except tk.TclError:pass
            self.map_link=None
        super().destroy()

