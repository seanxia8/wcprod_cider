import numpy as np
import sqlite3
import glob
import os

def get_config_dir():

    return os.path.join(os.path.dirname(__file__),'config')


def list_config(full_path=False):

    fs = glob.glob(os.path.join(get_config_dir(), '*.yaml'))

    if full_path:
        return fs

    return [os.path.basename(f)[:-5] for f in fs]


def get_config(name):

    options = list_config()
    results = list_config(True)

    if name in options:
        return results[options.index(name)]

    alt_name = name + '.yaml'
    if alt_name in options:
        return results[options.index(alt_name)]

    print('No data found for config name:',name)
    raise NotImplementedError

def positions(z_min,z_max,r_min,r_max,gap_size,nphi_initial=0,verbose=False):
    if r_min < 0 or r_max <= r_min:
        print('r_min must be positive and r_max must be larger than r_min')
        raise ValueError
    nz = int((z_max - z_min)/gap_size)+1
    nr = int((r_max - r_min)/gap_size)+1
    z_start = (z_max - z_min - (nz-1)*gap_size)/2. + z_min
    r_start = (r_max - r_min - (nr-1)*gap_size)/2. + r_min

    
    #if nphi_initial > 0:
    #    base_seg = 2 * np.pi / nphi_initial
    #    r_base = r_min + gap_size
        
    rphi_pts=[]
    for i in range(nr):
        #if nphi_initial == 0:
        r = r_start + i * gap_size
        if (2*np.pi*r) < 2*gap_size:
            continue
        n = int((2 * np.pi * r)/gap_size)
        #else:
        #r = r_start + gap
        #new_seg = base_seg * (r_base ** 2 - r_min ** 2) / (r ** 2 - r_start ** 2)
        #n = int((2 * np.pi) / new_seg + 0.5)
        pts = np.zeros(shape=(n,2),dtype=float)
        pts[:,0]=r
        pts[:,1]=np.arange(n)*(360./n)
        rphi_pts.append(pts)
        if verbose:
            print('r:',r,'...',n,'points')
    rphi_pts=np.concatenate(rphi_pts)
    batch = rphi_pts.shape[0]
    if verbose: print('Total points per plane:',batch)
    pts = np.zeros(shape=(nz*batch,3),dtype=float)
    if verbose: print('Total points in the volume:',pts.shape[0])
    for i in range(nz):
        z = z_start + i*gap_size
        start = i*batch
        end   = (i+1)*batch
        #pts[start:end,0:2]=rphi_pts
        pts[start:end,0] = rphi_pts[:,0] * np.cos(rphi_pts[:,1]*2*np.pi/360.)
        pts[start:end,1] = rphi_pts[:,0] * np.sin(rphi_pts[:,1]*2*np.pi/360.)
        pts[start:end,2] = z
    return pts

def voxels(z_min,z_max,r_min,r_max,gap_size,nphi_initial,verbose=False):

    #define the edges of voxels with the same volume
    
    if r_min < 0 or r_max <= r_min:
        print('r_min must be positive and r_max must be larger than r_min')
        raise ValueError
    if nphi_initial <= 0:
        print('To generate voxels, n_phi_start must be positive integer')
        raise ValueError
    
    nz = int((z_max - z_min)/gap_size)+1
    nr = int((r_max - r_min)/gap_size)+1
    z_start = z_min
    r_start = r_min

    rphi_pts=[]
    base_seg = 2 * np.pi / nphi_initial
    r_base = r_min + gap_size
    for i in range(nr):
        r = r_start + gap_size
        if r > r_max + 1.E-6:
            r = r_max
        new_seg = base_seg * (r_base**2 - r_min**2) / (r**2 - r_start**2)
        n = int((2 * np.pi) / new_seg + 0.5)
        
        pts = np.zeros(shape=(n,4),dtype=float)
        pts[:,0]=r_start
        pts[:,1]=r
        pts[:,2]=np.arange(n)*(360./n)
        pts[:,3]=np.arange(1, n+1)*(360./n)
        rphi_pts.append(pts)

        r_start = r
        if verbose:
            print('r:',r,'...',n,'points')
            
    rphi_pts=np.concatenate(rphi_pts)
    batch = rphi_pts.shape[0]
    if verbose: print('Total voxels per plane:',batch)
    
    vox = np.zeros(shape=(nz*batch,6),dtype=float)
    pts = np.zeros(shape=(nz*batch,3),dtype=float)
    
    if verbose: print('Total points in the volume:', len(vox))
    for i in range(nz):
        z = z_start + gap_size
        if z > z_max+1.E-6:
            z = z_max
        start = i*batch
        end   = (i+1)*batch
        vox[start:end,0:2] = rphi_pts[:,0:2]
        vox[start:end,2:4] = rphi_pts[:,2:]
        vox[start:end,4:6] = [z_start, z]        

        pts[start:end, 0] = 0.5*(rphi_pts[:,0]+rphi_pts[:,1]) * np.cos(0.5*(rphi_pts[:,2]+rphi_pts[:,3])*np.pi/180.)
        pts[start:end, 1] = 0.5*(rphi_pts[:,0]+rphi_pts[:,1]) * np.sin(0.5*(rphi_pts[:,2]+rphi_pts[:,3])*np.pi/180.)
        pts[start:end, 2] = 0.5*(z + z_start)

        z_start = z

    return vox, pts


def directions(gap_angle, nphi_initial=0):
    if nphi_initial > 0:
        return np.array([[0,0]])

    nphi = int(360/gap_angle)
    ntheta = int(180/gap_angle)+1
    
    phi_start   = (360 - gap_angle*(nphi)) / 2.
    theta_start = (180 - gap_angle*(ntheta-1)) / 2.
    phi_v   = phi_start + np.arange(nphi)*gap_angle
    theta_v = theta_start + np.arange(ntheta)*gap_angle
    grid = np.meshgrid(theta_v,phi_v)
    return np.column_stack([grid[0].flatten(),grid[1].flatten()])


def coordinates(points, dirs):
    idx_pts=np.arange(points.shape[0])
    idx_dir=np.arange(dirs.shape[0])
    
    mesh = np.meshgrid(idx_pts,idx_dir)
    mesh = np.column_stack([mesh[0].flatten(),mesh[1].flatten()])
    
    coords = np.zeros(shape=(len(idx_pts) * len(idx_dir),7),dtype=float)
    coords[:,0:3] = points[mesh[:,0]]
    coords[:,3:5] = dirs[mesh[:,1]]
    coords[:,5]   = mesh[:,0]
    coords[:,6]   = mesh[:,1]
    return coords

def volumes(voxels):

    idx = np.arange(len(voxels))

    vols = np.zeros(shape=(len(voxels),7),dtype=float)
    vols[:,0:6] = voxels
    vols[:,6]   = idx

    return vols
    
