"""Independent bidirectional XY link; does not replace existing map bindings."""
import numpy as np


class ApPPDMapLink:
    def __init__(self,viewer,image_frame,vertices):
        self.viewer=viewer;self.frame=image_frame;self.canvas=image_frame.canvas
        self.vertices=np.asarray(vertices,float)
        if self.vertices.ndim!=2 or self.vertices.shape[1]!=2 or len(self.vertices)<2 or not np.isfinite(self.vertices).all():
            raise ValueError('Map link needs finite polysection vertices.')
        self.delta=np.diff(self.vertices,axis=0);self.length=np.linalg.norm(self.delta,axis=1)
        if np.any(self.length<=0):raise ValueError('Remove repeated consecutive polysection vertices.')
        self.chain=np.r_[0,np.cumsum(self.length)]
        self.tag='ap_ppd_cursor_'+str(id(self));self.enabled=True;self.point=None
        if not hasattr(image_frame,'ap_ppd_cursor_links'):image_frame.ap_ppd_cursor_links=[]
        image_frame.ap_ppd_cursor_links.append(self)
        self.figure_binding=viewer.section_canvas.canvas.mpl_connect('motion_notify_event',self.section_motion)

    def section_motion(self,event):
        if not self.enabled or event.inaxes is not self.viewer.section_canvas.ax or self.viewer.section_canvas.toolbar.mode:return
        d=float(np.clip(event.xdata,self.chain[0],self.chain[-1]));k=min(np.searchsorted(self.chain,d,side='right')-1,len(self.length)-1)
        self.point=self.vertices[k]+self.delta[k]*(d-self.chain[k])/self.length[k]
        self.draw();self.viewer.set_cursor(d)

    def draw(self):
        if self.point is None:return
        x,y=self.frame.global_to_canvas_coor(*self.point);self.canvas.delete(self.tag)
        self.canvas.create_oval(x-5,y-5,x+5,y+5,outline='cyan',width=2,tags=self.tag)

    def map_position(self,x,y):
        if not self.enabled:return
        p=np.array([x,y]);a=self.vertices[:-1]
        u=np.clip(np.sum((p-a)*self.delta,axis=1)/self.length**2,0,1)
        q=a+u[:,None]*self.delta;k=int(np.argmin(np.sum((q-p)**2,axis=1)))
        self.point=q[k]
        self.viewer.set_cursor(self.chain[k]+u[k]*self.length[k]);self.draw()

    def close(self):
        if self in self.frame.ap_ppd_cursor_links:self.frame.ap_ppd_cursor_links.remove(self)
        self.canvas.delete(self.tag)
        self.viewer.section_canvas.canvas.mpl_disconnect(self.figure_binding)
