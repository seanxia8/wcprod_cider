import os, yaml
from .utils import positions, directions, voxels, coordinates, volumes

class wcprod_project:
        
    def __init__(self,cfg=None):
                
        if cfg: self.configure(cfg)
        
    def configure(self,cfg):
        
        if type(cfg) == str:
            if os.path.isfile(cfg):
                cfg=yaml.safe_load(open(cfg,'r'))
            else:
                cfg=yaml.safe_load(cfg)
        assert type(cfg) == dict

        self._project = str(cfg['project'])
        self._rmin    = float(cfg['rmin'])
        self._rmax    = float(cfg['rmax'])
        self._zmin    = float(cfg['zmin'])
        self._zmax    = float(cfg['zmax'])
        self._gap_space = float(cfg['gap_space'])
        self._gap_angle = float(cfg['gap_angle'])
        self._n_phi_start = int(cfg.get('n_phi_start', 0))
        self._num_photons = int(cfg['num_photons'])        
        self._positions  = positions(self.zmin,self.zmax,self.rmin,self.rmax,self.gap_space)
        self._directions = directions(self.gap_angle)
        
        if self._n_phi_start == 0:
            self._configs    = coordinates(self.positions,self.directions)
        else:
            self._voxels, self._positions = voxels(self.zmin,self.zmax,self.rmin,self.rmax,self.gap_space,self.n_phi_start)
            nz = int((self.zmax - self.zmin)/self.gap_space)+1
            self._configs    = volumes(self.voxels)
            
    def __str__(self):
        msg=f'''
        Project name: {self.project}
        Cylinder geometry
          R: {self.rmin} => {self.rmax}
          Z: {self.zmin} => {self.zmax}
        Gap space: {self.gap_space}
        Gap angle: {self.gap_angle}
        Starting n phi: {self.n_phi_start}
        Sampling points: {self.positions.shape[0]}
        Sampling directions: {self.directions.shape[0]}
        Sampling configs: {self.configs.shape[0]}
        Photons per config: {self.num_photons} 
        '''
        return msg    
    
    @property
    def zmin(self): return self._zmin
    @property
    def zmax(self): return self._zmax
    @property
    def rmin(self): return self._rmin
    @property
    def rmax(self): return self._rmax
    @property
    def gap_space(self): return self._gap_space
    @property
    def gap_angle(self): return self._gap_angle
    @property
    def n_phi_start(self): return self._n_phi_start
    @property
    def project(self): return self._project
    @property
    def positions(self): return self._positions
    @property
    def directions(self): return self._directions
    @property
    def voxels(self): return self._voxels
    @property
    def configs(self): return self._configs
    @property
    def num_photons(self): return self._num_photons

    def draw_dir(self):
        import plotly.graph_objects as go
        import numpy as np
        dirs = self.directions
        zs=np.cos(dirs[:,0]/180.*np.pi)
        xs=np.sin(dirs[:,0]/180.*np.pi)*np.cos(dirs[:,1]/360*2*np.pi)
        ys=np.sin(dirs[:,0]/180.*np.pi)*np.sin(dirs[:,1]/360*2*np.pi)


        trace=go.Scatter3d(x=xs, y=ys, z=zs,
                           mode='markers',
                           marker=dict(size=1,opacity=0.5),
                          )

        fig=go.Figure(data=trace)
        return fig

    def draw_pos(self):
        import plotly.graph_objects as go
        pts = self.positions
        trace=go.Scatter3d(x=pts[:,0],
                           y=pts[:,1],
                           z=pts[:,2],
                           mode='markers',
                           marker=dict(size=1,opacity=0.5),
                          )
        fig=go.Figure(data=trace)
        return fig

    def draw_vox_plane(self):
        import plotly.graph_objects as go
        import numpy as np
        vox = self.voxels[np.where(self.voxels[:,4]==0)]
        x_coords = [ [vox[i,0]*np.cos(vox[i,2]), vox[i,1]*np.cos(vox[i,2]), vox[i,1]*np.cos(vox[i,3]), vox[i,0]*np.cos(vox[i,3])] for i in range(len(vox))]
        y_coords = [ [vox[i,0]*np.sin(vox[i,2]), vox[i,1]*np.sin(vox[i,2]), vox[i,1]*np.sin(vox[i,3]), vox[i,0]*np.sin(vox[i,3])] for i in range(len(vox))]

        fig = go.Figure()

        colors = [
            'rgba(0, 0, 255, 0.7)',  # Blue with 70% opacity
            'rgba(0, 255, 255, 0.9)'  # Cyan with 90% opacity
        ]
        
        for i in range(len(vox)):
            x = x_coords[i] + [x_coords[i][0]]
            y = y_coords[i] + [y_coords[i][0]]

            fig.add_trace(go.Scatter(
                x=x,y=y,
                fill='toself',
                line=dict(color='royalblue'),
                fillcolor=colors[i%len(colors)],
                mode='lines',
                name=f'Trapezoid {i+1}'
                ))
                    
        return fig
        
        
