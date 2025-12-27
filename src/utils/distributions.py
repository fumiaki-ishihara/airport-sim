"""Statistical distributions for simulation."""

from typing import Optional
import numpy as np
from scipy import stats


class TruncatedTDistribution:
    """
    Truncated t-distribution for arrival time generation.
    
    Generates samples from a t-distribution truncated to a specified range.
    Uses rejection sampling to ensure all samples fall within bounds.
    """
    
    def __init__(
        self,
        df: float = 7,
        loc: float = 70,
        scale: float = 20,
        lower: float = 20,
        upper: float = 120,
        random_state: Optional[int] = None,
    ):
        """
        Initialize truncated t-distribution.
        
        Args:
            df: Degrees of freedom for t-distribution
            loc: Location parameter (mean minutes before departure)
            scale: Scale parameter
            lower: Lower bound (minimum minutes before departure)
            upper: Upper bound (maximum minutes before departure)
            random_state: Random seed for reproducibility
        """
        self.df = df
        self.loc = loc
        self.scale = scale
        self.lower = lower
        self.upper = upper
        
        # Create scipy t-distribution
        self.t_dist = stats.t(df=df, loc=loc, scale=scale)
        
        # Set random state
        if random_state is not None:
            np.random.seed(random_state)
    
    def sample(self, size: int = 1) -> np.ndarray:
        """
        Generate samples from the truncated distribution.
        
        Uses rejection sampling to ensure all values fall within bounds.
        
        Args:
            size: Number of samples to generate
        
        Returns:
            Array of samples (minutes before departure)
        """
        samples = []
        max_attempts = size * 100  # Prevent infinite loop
        attempts = 0
        
        while len(samples) < size and attempts < max_attempts:
            # Generate batch of candidates
            batch_size = (size - len(samples)) * 2
            candidates = self.t_dist.rvs(size=batch_size)
            
            # Filter to valid range
            valid = candidates[(candidates >= self.lower) & (candidates <= self.upper)]
            samples.extend(valid.tolist())
            attempts += batch_size
        
        if len(samples) < size:
            # Fill remaining with uniform if rejection sampling fails
            remaining = size - len(samples)
            uniform_samples = np.random.uniform(self.lower, self.upper, remaining)
            samples.extend(uniform_samples.tolist())
        
        return np.array(samples[:size])
    
    def sample_one(self) -> float:
        """Generate a single sample."""
        return float(self.sample(1)[0])
    
    def pdf(self, x: np.ndarray) -> np.ndarray:
        """
        Probability density function (normalized for truncation).
        
        Args:
            x: Points to evaluate
        
        Returns:
            Density values
        """
        # Calculate normalization constant
        cdf_upper = self.t_dist.cdf(self.upper)
        cdf_lower = self.t_dist.cdf(self.lower)
        norm_const = cdf_upper - cdf_lower
        
        # Calculate truncated PDF
        pdf = self.t_dist.pdf(x) / norm_const
        
        # Zero outside bounds
        pdf = np.where((x >= self.lower) & (x <= self.upper), pdf, 0)
        
        return pdf
    
    def cdf(self, x: np.ndarray) -> np.ndarray:
        """
        Cumulative distribution function (normalized for truncation).
        
        Args:
            x: Points to evaluate
        
        Returns:
            CDF values
        """
        cdf_upper = self.t_dist.cdf(self.upper)
        cdf_lower = self.t_dist.cdf(self.lower)
        norm_const = cdf_upper - cdf_lower
        
        # Calculate truncated CDF
        cdf = (self.t_dist.cdf(x) - cdf_lower) / norm_const
        
        # Clamp to [0, 1]
        cdf = np.clip(cdf, 0, 1)
        
        return cdf


class ServiceTimeDistribution:
    """Distribution for service times at various processes."""
    
    def __init__(
        self,
        mean: float,
        std: float,
        min_time: float = 1.0,
        random_state: Optional[int] = None,
    ):
        """
        Initialize service time distribution.
        
        Uses a normal distribution truncated at min_time.
        
        Args:
            mean: Mean service time in seconds
            std: Standard deviation in seconds
            min_time: Minimum service time (prevents negative)
            random_state: Random seed
        """
        self.mean = mean
        self.std = std
        self.min_time = min_time
        
        if random_state is not None:
            np.random.seed(random_state)
    
    def sample(self, size: int = 1) -> np.ndarray:
        """
        Generate service time samples.
        
        Args:
            size: Number of samples
        
        Returns:
            Array of service times in seconds
        """
        samples = np.random.normal(self.mean, self.std, size)
        samples = np.maximum(samples, self.min_time)
        return samples
    
    def sample_one(self) -> float:
        """Generate a single service time."""
        return float(self.sample(1)[0])


