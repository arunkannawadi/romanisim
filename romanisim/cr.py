import numpy as np
import scipy.interpolate as interpolate


def create_sampler(pdf, x):
    """A function for performing inverse transform sampling.
    
    Parameters
    ----------
    pdf : callable
        A function or empirical set of tabulated values which can 
        be used to call or evaluate `x`.
    x : 1-d array of floats
        A grid of values where the pdf should be evaluated.

    Returns
    -------
    inverse_cdf : 1-d array of floats
        The cumulative distribution function which allows sampling
        from the `pdf` distribution within the bounds described
        by the grid `x`.
    """
    
    y = pdf(x)                        
    cdf_y = np.cumsum(y) - y[0]          
    cdf_y /= cdf_y.max()       
    inverse_cdf = interpolate.interp1d(cdf_y, x)
    return inverse_cdf


def moyal_distribution(x, location=1000, scale=300):
    """Return unnormalized Moyal distribution, which approximates a 
    Landau distribution and is used to describe the energy loss 
    probability distribution of a charged particle through a detector.

    Parameters
    ----------
    x : 1-d array
        An array of dE/dx values (units: eV/micron) that forms the
        grid on which the Moyal distribution will be evaluated.
    location : float
        The peak location of the distribution, units of eV / micron.
    scale : float
        A width parameter for the distribution, units of eV / micron.
    Returns
    -------
    moyal : 1-d array of floats
        Moyal distribution (pdf) evaluated on `x` grid of points.
    """
    xs = (x - location) / scale
    moyal = np.exp(-(xs + np.exp(-xs)) / 2) 
    return moyal


def power_law_distribution(x, slope=-4.33):
    """Return unnormalized power-law distribution parameterized by
    a log-log slope, used to describe the cosmic ray path lengths.

    Parameters
    ----------
    x : 1-d array of floats
        An array of cosmic ray path lengths (units: micron).
    slope : float
        The log-log slope of the distribution, default based on
        Miles et al. (2021).
    
    Returns
    -------
    power_law : 1-d array of floats
        Power-law distribution (pdf) evaluated on `x` grid of points.
    """
    power_law = np.power(x, slope)
    return power_law


def sample_cr_params(
    N_samples, 
    N_i=4096, 
    N_j=4096, 
    min_dEdx=10,
    max_dEdx=10000,
    min_cr_len=10, 
    max_cr_len=2000, 
    grid_size=10000,
    rng=None,
    seed=48,
):
    """Generates cosmic ray parameters randomly sampled from distribution.
    One might re-implement this by reading in parameters from a reference
    file, or something similar.

    Parameters
    ----------
    N_samples : int 
        Number of CRs to generate.
    N_x : int
        Number of pixels along x-axis of detector
    N_y : int
        Number of pixels along y-axis of detector
    min_dEdx : float
        Minimum value of CR energy loss (dE/dx), units of eV / micron.
    max_dEdx : float
        Maximum value of CR energy loss (dE/dx), units of eV / micron.
    min_cr_len : float
        Minimum length of cosmic ray trail, units of micron.
    max_cr_len : float
        Maximum length of cosmic ray trail, units of micron.
    grid_size : int
        Number of points on the cosmic ray length and energy loss grids.
        Increasing this parameter increases the level of sampling for
        the distributions.
    rng : np.random.Generator
        Random number generator to use
    seed : int
        seed to use for random number generator

    Returns
    -------
    cr_x : float, between 0 and N_x-1
        x pixel coordinate of cosmic ray, units of pixels.
    cr_y : float between 0 and N_y-1
        y pixel coordinate of cosmic ray, units of pixels.
    cr_phi : float between 0 and 2pi
        Direction of cosmic ray, units of radians.
    cr_length : float
        Cosmic ray length, units of micron.
    cr_dEdx : float
        Cosmic ray energy loss, units of eV / micron.
    """

    if rng is None:
        rng = np.random.default_rng(seed)

    # sample CR positions [pix]
    cr_i, cr_j = (rng.random(size=(N_samples, 2)) * (N_i, N_j)).transpose()

    # sample CR direction [radian]
    cr_phi = rng.random(N_samples) * 2 * np.pi

    # sample path lengths [micron] 
    len_grid = np.linspace(min_cr_len, max_cr_len, grid_size)
    inv_cdf_len = create_sampler(power_law_distribution, len_grid)
    cr_length = inv_cdf_len(rng.random(N_samples))

    # sample energy losses [eV/micron]
    dEdx_grid = np.linspace(min_dEdx, max_dEdx, grid_size)
    inv_cdf_dEdx = create_sampler(moyal_distribution, dEdx_grid)
    cr_dEdx = inv_cdf_dEdx(rng.random(N_samples))

    return cr_i, cr_j, cr_phi, cr_length, cr_dEdx


def traverse(trail_start, trail_end, N_i=4096, N_j=4096):
    """Given a starting and ending pixel, returns a list of pixel 
    coordinates (ii, jj) and their traversed path lengths.

    Parameters
    ----------
    trail_start: two-element array of floats
        The starting coordinates in (i, j) of the cosmic ray trail, 
        in units of pix.
    trail_end: two-element array of floats, units of pix
        The ending coordinates in (i, j) of the cosmic ray trail, in 
        units of pix.

    Returns
    -------
    ii : 1-d int array of shape N
        i-axis positions of traversed trail, in units of pix.
    jj : 1-d array of shape N
        j-axis positions of traversed trail, in units of pix.
    lengths : 1-d array of shape N
        Chord lengths for each traversed pixel, in units of pix. 
    """

    # increase in i-direction
    if trail_start[0] < trail_end[0]:
        i0, j0 = trail_start
        i1, j1 = trail_end
    else:
        i1, j1 = trail_start
        i0, j0 = trail_end
    
    di = i1 - i0
    dj = j1 - j0

    # border crossing in j
    cross_i = np.array([i0, j0], dtype=float)
    if di != 0:
        borders_i = np.sign(di) * np.arange(
            0, np.floor(np.absolute(di) + 1)).reshape(-1, 1)
        step_i = np.array([[1, (dj / di)]])
        cross_i = cross_i + borders_i @ step_i
    
    # border crossing in i
    cross_j = np.array([i0, j0], dtype=float)
    if dj != 0:
        borders_j = np.sign(dj) * np.arange(
            0, np.floor(np.absolute(dj) + 1)).reshape(-1, 1)
        step_j = np.array([[(di / dj), 1]])
        cross_j = cross_j + borders_j @ step_j

    # sort by i-axis and remove duplicates
    crossings = np.vstack((cross_i, cross_j))
    crossings = crossings[np.argsort(crossings[:, 0])]
    crossings = np.unique(crossings, axis=0)

    # remove pixels that go outside detector edge
    outside = (
        (crossings[:, 0] < 0) | (crossings[:, 0] > N_i) |
        (crossings[:, 1] < 0) | (crossings[:, 1] > N_j)
    )
    crossings = crossings[~outside]

    # compute traversed distances over pixels
    if len(crossings) > 1:
        # convenient for the next few lines
        crossings_pixel = np.floor(crossings)

        ii, jj = crossings_pixel.astype(int).T

        # compute final trail length and remove if 0
        last_diff = (crossings - crossings_pixel)[-1]
        if np.isclose(last_diff, 0).all():
            ii = ii[:-1]
            jj = jj[:-1]
            diffs = np.diff(crossings, axis=0)
        else:
            diffs = np.vstack([np.diff(crossings, axis=0), last_diff])
            lengths = ((diffs ** 2).sum(1) ** 0.5)
    else:
        ii, jj = np.floor(crossings).astype(int).T
        lengths = np.array([(di ** 2 + dj ** 2) ** 0.5])

    return ii, jj, lengths

    
def simulate_crs(image, time, flux=8, area=0.168, gain=3.8, pixel_size=10,
                 pixel_depth=5, rng=None, seed=47):
    """Adds CRs to an existing image.
    
    Parameters
    ----------
    image : 2-d array of floats
        The detector image with values in units of counts.
    time : float
        The exposure time, units of s.
    flux : float
        Cosmic ray flux, units of cm^-2 s^-1. Default value of 8 
        is equal to the value assumed by the JWST ETC.
    area : float
        The area of the WFI detector, units of cm^2.
    gain : float
        The gain to convert from eV to counts, units of eV / counts.
    pixel_size : float
        The size of an individual pixel in the detector, units of micron.
    pixel_depth : float
        The depth of an individual pixel in the detector, units of micron.
    rng : np.random.Generator
        Random number generator to use
    seed : int
        seed to use for random number generator
    
    Returns
    -------
    image : 2-d array of floats
        The detector image, in units of counts, updated to include
        all of the generated cosmic ray hits.
    """

    if rng is None:
        rng = np.random.default_rng(seed)

    N_i, N_j = image.shape
    N_samples = rng.poisson(flux * area * time)
    cr_i0, cr_j0, cr_angle, cr_length, cr_dEdx = sample_cr_params(
        N_samples, N_i=N_i, N_j=N_j, rng=rng)

    cr_length = cr_length / pixel_size
    cr_i1 = (cr_i0 + cr_length * np.cos(cr_angle)).clip(1, N_i - 1)
    cr_j1 = (cr_j0 + cr_length * np.sin(cr_angle)).clip(1, N_j - 1)

    # go from eV/micron -> counts/pixel
    cr_counts_per_pix = cr_dEdx * pixel_size / gain
    im1 = image.copy()
    for i0, j0, i1, j1, counts_per_pix in zip(
            cr_i0, cr_j0, cr_i1, cr_j1, cr_counts_per_pix):
        ii, jj, length_2d = traverse([i0, j0], [i1, j1])
        length_3d = ((pixel_depth / pixel_size) ** 2 + length_2d ** 2) ** 0.5
        image[ii, jj] += rng.poisson(counts_per_pix * length_3d)
        if np.any((jj == 76) & (ii == 54)):
            import pdb
            pdb.set_trace()

    return image


if __name__ == "__main__":
    # initialize a detector
    image = np.zeros((4096, 4096), dtype=float)

    flux = 8 # events/cm^2/s
    area = 0.168 # cm^2
    t_exp = 3.04 # s

    # simulate 500 resultant frames
    for _ in range(500):
        image = simulate_crs(image, flux, area, t_exp)
