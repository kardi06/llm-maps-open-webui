/**
 * Google Maps URL Generation Utilities
 * Provides centralized functions for generating Google Maps URLs for various actions
 */

/**
 * Generate a Google Maps URL for a specific place using place ID
 */
export function generatePlaceUrl(placeId: string): string {
	if (!placeId) {
		throw new Error('Place ID is required');
	}
	return `https://maps.google.com/maps/place/?q=place_id:${encodeURIComponent(placeId)}`;
}

/**
 * Generate a Google Maps search URL for a query
 */
export function generateSearchUrl(query: string, lat?: number, lng?: number): string {
	if (!query) {
		throw new Error('Search query is required');
	}
	
	const encodedQuery = encodeURIComponent(query);
	
	if (lat !== undefined && lng !== undefined) {
		return `https://maps.google.com/maps/search/${encodedQuery}/@${lat},${lng},15z`;
	}
	
	return `https://maps.google.com/maps/search/${encodedQuery}`;
}

/**
 * Generate a Google Maps directions URL
 */
export function generateDirectionsUrl(
	origin: string,
	destination: string,
	travelMode: 'driving' | 'walking' | 'transit' | 'bicycling' = 'driving'
): string {
	if (!origin || !destination) {
		throw new Error('Both origin and destination are required');
	}
	
	const encodedOrigin = encodeURIComponent(origin);
	const encodedDestination = encodeURIComponent(destination);
	const mode = travelMode.toLowerCase();
	
	return `https://maps.google.com/maps/dir/${encodedOrigin}/${encodedDestination}?travelmode=${mode}`;
}

/**
 * Generate a Google Maps directions URL with coordinates
 */
export function generateDirectionsUrlWithCoords(
	originLat: number,
	originLng: number,
	destLat: number,
	destLng: number,
	travelMode: 'driving' | 'walking' | 'transit' | 'bicycling' = 'driving'
): string {
	const mode = travelMode.toLowerCase();
	return `https://maps.google.com/maps/dir/${originLat},${originLng}/${destLat},${destLng}?travelmode=${mode}`;
}

/**
 * Generate a Google Maps URL for a place using name and address
 */
export function generatePlaceSearchUrl(name: string, address: string): string {
	if (!name) {
		throw new Error('Place name is required');
	}
	
	const query = address ? `${name} ${address}` : name;
	return generateSearchUrl(query);
}

/**
 * Generate a Google Maps Embed API URL for iframe embedding
 */
export function generateEmbedUrl(
	apiKey: string,
	mode: 'place' | 'search' | 'directions' | 'view',
	params: {
		// For place mode
		placeId?: string;
		// For search mode
		query?: string;
		// For directions mode
		origin?: string;
		destination?: string;
		// For view mode
		center?: string;
		zoom?: number;
		// Common params
		maptype?: 'roadmap' | 'satellite';
		language?: string;
		region?: string;
	}
): string {
	if (!apiKey) {
		throw new Error('API key is required for embed URLs');
	}
	
	const baseUrl = 'https://www.google.com/maps/embed/v1';
	const urlParams = new URLSearchParams();
	
	urlParams.set('key', apiKey);
	
	// Add common parameters
	if (params.maptype) {
		urlParams.set('maptype', params.maptype);
	}
	if (params.language) {
		urlParams.set('language', params.language);
	}
	if (params.region) {
		urlParams.set('region', params.region);
	}
	
	switch (mode) {
		case 'place':
			if (!params.placeId && !params.query) {
				throw new Error('Either placeId or query is required for place mode');
			}
			if (params.placeId) {
				urlParams.set('q', `place_id:${params.placeId}`);
			} else if (params.query) {
				urlParams.set('q', params.query);
			}
			break;
			
		case 'search':
			if (!params.query) {
				throw new Error('Query is required for search mode');
			}
			urlParams.set('q', params.query);
			break;
			
		case 'directions':
			if (!params.origin || !params.destination) {
				throw new Error('Both origin and destination are required for directions mode');
			}
			urlParams.set('origin', params.origin);
			urlParams.set('destination', params.destination);
			break;
			
		case 'view':
			if (params.center) {
				urlParams.set('center', params.center);
			}
			if (params.zoom) {
				urlParams.set('zoom', params.zoom.toString());
			}
			break;
			
		default:
			throw new Error(`Unsupported embed mode: ${mode}`);
	}
	
	return `${baseUrl}/${mode}?${urlParams.toString()}`;
}

/**
 * Validate coordinates
 */
export function validateCoordinates(lat: number, lng: number): boolean {
	return (
		typeof lat === 'number' &&
		typeof lng === 'number' &&
		lat >= -90 &&
		lat <= 90 &&
		lng >= -180 &&
		lng <= 180 &&
		!isNaN(lat) &&
		!isNaN(lng)
	);
}

/**
 * Validate travel mode
 */
export function validateTravelMode(mode: string): mode is 'driving' | 'walking' | 'transit' | 'bicycling' {
	return ['driving', 'walking', 'transit', 'bicycling'].includes(mode.toLowerCase());
}

/**
 * Parse coordinates from a string like "lat,lng"
 */
export function parseCoordinates(coordString: string): { lat: number; lng: number } | null {
	if (!coordString || typeof coordString !== 'string') {
		return null;
	}
	
	const parts = coordString.split(',').map(part => parseFloat(part.trim()));
	
	if (parts.length !== 2 || parts.some(isNaN)) {
		return null;
	}
	
	const [lat, lng] = parts;
	
	if (!validateCoordinates(lat, lng)) {
		return null;
	}
	
	return { lat, lng };
}

/**
 * Format coordinates as a string for URLs
 */
export function formatCoordinates(lat: number, lng: number): string {
	if (!validateCoordinates(lat, lng)) {
		throw new Error('Invalid coordinates');
	}
	
	return `${lat.toFixed(6)},${lng.toFixed(6)}`;
}

/**
 * Generate a shareable Google Maps URL with multiple options
 */
export function generateShareableUrl(options: {
	type: 'place' | 'search' | 'directions';
	placeId?: string;
	query?: string;
	placeName?: string;
	address?: string;
	origin?: string;
	destination?: string;
	lat?: number;
	lng?: number;
	zoom?: number;
	travelMode?: 'driving' | 'walking' | 'transit' | 'bicycling';
}): string {
	const { type } = options;
	
	switch (type) {
		case 'place':
			if (options.placeId) {
				return generatePlaceUrl(options.placeId);
			} else if (options.placeName) {
				return generatePlaceSearchUrl(options.placeName, options.address || '');
			} else if (options.query) {
				return generateSearchUrl(options.query, options.lat, options.lng);
			}
			throw new Error('Place type requires placeId, placeName, or query');
			
		case 'search':
			if (!options.query) {
				throw new Error('Search type requires query');
			}
			return generateSearchUrl(options.query, options.lat, options.lng);
			
		case 'directions':
			if (!options.origin || !options.destination) {
				throw new Error('Directions type requires origin and destination');
			}
			return generateDirectionsUrl(
				options.origin,
				options.destination,
				options.travelMode || 'driving'
			);
			
		default:
			throw new Error(`Unsupported URL type: ${type}`);
	}
} 