<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { formatRating, getRatingStars, validateCoordinates } from '$lib/utils/maps';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let id: string;
	export let data: {
		places: Array<{
			name: string;
			address: string;
			lat: number | null;
			lng: number | null;
			place_id?: string;
			rating?: number;
			open_now?: boolean;
			maps_url?: string;
		}>;
		query?: string;
		total_results?: number;
		search_location?: string;
		search_radius?: string;
	};

	// Validate and filter places with valid data
	$: validPlaces = data.places.filter(place => {
		// Require at least name and address
		return place.name && place.address && place.name.trim() !== '' && place.address.trim() !== '';
	});

	// Separate places with valid coordinates from those without
	$: placesWithCoords = validPlaces.filter(place => 
		place.lat !== null && place.lng !== null && validateCoordinates(place.lat, place.lng)
	);

	$: placesWithoutCoords = validPlaces.filter(place => 
		place.lat === null || place.lng === null || !validateCoordinates(place.lat || 0, place.lng || 0)
	);

	const generateMapsUrl = (place: any): string => {
		if (place.maps_url) {
			return place.maps_url;
		}
		if (place.place_id) {
			return `https://maps.google.com/maps/place/?q=place_id:${encodeURIComponent(place.place_id)}`;
		}
		// Fallback to search by name and address
		const searchQuery = `${place.name} ${place.address}`.trim();
		return `https://maps.google.com/maps/search/${encodeURIComponent(searchQuery)}`;
	};

	const openInGoogleMaps = (place: any) => {
		const url = generateMapsUrl(place);
		window.open(url, '_blank', 'noopener,noreferrer');
	};

	const formatCoordinates = (lat: number | null, lng: number | null): string => {
		if (lat === null || lng === null) return '';
		if (!validateCoordinates(lat, lng)) return '';
		return `${lat.toFixed(6)}, ${lng.toFixed(6)}`;
	};

	const hasValidLocation = (place: any): boolean => {
		return place.lat !== null && place.lng !== null && validateCoordinates(place.lat, place.lng);
	};

	const getPlaceStatusColor = (place: any): string => {
		if (place.open_now === true) return 'text-green-600 dark:text-green-400';
		if (place.open_now === false) return 'text-red-600 dark:text-red-400';
		return 'text-gray-500 dark:text-gray-400';
	};

	const getPlaceStatusText = (place: any): string => {
		if (place.open_now === true) return $i18n.t('Open');
		if (place.open_now === false) return $i18n.t('Closed');
		return $i18n.t('Hours unknown');
	};
</script>

<div class="w-full my-3">
	<!-- Header -->
	{#if data.query}
		<div class="mb-3">
			<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100">
				{$i18n.t('Places for "{{query}}"', { query: data.query })}
			</h3>
			<div class="flex flex-wrap items-center gap-4 text-sm text-gray-600 dark:text-gray-400 mt-1">
				<span>
					{$i18n.t('Showing {{count}} results', { count: validPlaces.length })}
					{#if data.total_results && data.total_results > validPlaces.length}
						{$i18n.t('of {{total}}', { total: data.total_results })}
					{/if}
				</span>
				{#if data.search_location}
					<span>• {$i18n.t('Near {{location}}', { location: data.search_location })}</span>
				{/if}
				{#if data.search_radius}
					<span>• {$i18n.t('Within {{radius}}', { radius: data.search_radius })}</span>
				{/if}
			</div>
			
			<!-- Data Quality Info -->
			{#if placesWithoutCoords.length > 0}
				<div class="mt-2 p-2 bg-yellow-50 dark:bg-yellow-900/20 border border-yellow-200 dark:border-yellow-800 rounded text-sm">
					<div class="flex items-start gap-2">
						<svg class="w-4 h-4 text-yellow-500 flex-shrink-0 mt-0.5" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
							<path fill-rule="evenodd" d="M8.485 3.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 3.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
						</svg>
						<div>
							<span class="text-yellow-800 dark:text-yellow-200 font-medium">
								{$i18n.t('{{count}} places have incomplete location data', { count: placesWithoutCoords.length })}
							</span>
							<span class="text-yellow-700 dark:text-yellow-300 ml-1">
								{$i18n.t('and may not appear accurately on map services.')}
							</span>
						</div>
					</div>
				</div>
			{/if}
		</div>
	{/if}

	<!-- Places Grid -->
	{#if validPlaces.length > 0}
		<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
			{#each validPlaces as place, idx}
				<div
					class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 hover:shadow-lg transition-shadow duration-200"
					role="article"
					aria-label="{$i18n.t('Place details for {{name}}', { name: place.name })}"
				>
					<!-- Place Name and Rating -->
					<div class="flex justify-between items-start mb-2">
						<h4 class="font-semibold text-gray-900 dark:text-gray-100 text-sm leading-tight pr-2 flex-1">
							{place.name}
						</h4>
						{#if place.rating}
							<div class="flex items-center gap-1 flex-shrink-0">
								<span class="text-yellow-400 text-sm" aria-hidden="true">
									{getRatingStars(place.rating)}
								</span>
								<span class="text-sm text-gray-600 dark:text-gray-400">
									{formatRating(place.rating)}
								</span>
							</div>
						{/if}
					</div>

					<!-- Address -->
					<p class="text-sm text-gray-600 dark:text-gray-400 mb-2 line-clamp-2">
						{place.address}
					</p>

					<!-- Coordinates Display (if valid) -->
					{#if hasValidLocation(place)}
						<div class="text-xs text-gray-500 dark:text-gray-500 mb-3 font-mono">
							📍 {formatCoordinates(place.lat, place.lng)}
						</div>
					{:else}
						<div class="text-xs text-orange-600 dark:text-orange-400 mb-3 flex items-center gap-1">
							<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
								<path fill-rule="evenodd" d="M8.485 3.495c.673-1.167 2.357-1.167 3.03 0l6.28 10.875c.673 1.167-.17 2.625-1.516 2.625H3.72c-1.347 0-2.189-1.458-1.515-2.625L8.485 3.495zM10 6a.75.75 0 01.75.75v3.5a.75.75 0 01-1.5 0v-3.5A.75.75 0 0110 6zm0 9a1 1 0 100-2 1 1 0 000 2z" clip-rule="evenodd" />
							</svg>
							{$i18n.t('Location data unavailable')}
						</div>
					{/if}

					<!-- Status and Actions -->
					<div class="flex justify-between items-center">
						<!-- Open Status -->
						<div class="flex items-center gap-1">
							<div
								class="w-2 h-2 rounded-full {place.open_now === true
									? 'bg-green-500'
									: place.open_now === false
									? 'bg-red-500'
									: 'bg-gray-400'}"
								aria-hidden="true"
							></div>
							<span class="text-xs {getPlaceStatusColor(place)}">
								{getPlaceStatusText(place)}
							</span>
						</div>

						<!-- Open in Google Maps Button -->
						<button
							type="button"
							class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors duration-150"
							on:click={() => openInGoogleMaps(place)}
							aria-label="{$i18n.t('Open {{name}} in Google Maps', { name: place.name })}"
						>
							<svg
								class="w-3 h-3"
								fill="currentColor"
								viewBox="0 0 20 20"
								xmlns="http://www.w3.org/2000/svg"
								aria-hidden="true"
							>
								<path
									fill-rule="evenodd"
									d="M4.25 5.5a.75.75 0 00-.75.75v8.5c0 .414.336.75.75.75h8.5a.75.75 0 00.75-.75v-4a.75.75 0 011.5 0v4A2.25 2.25 0 0112.75 17h-8.5A2.25 2.25 0 012 14.75v-8.5A2.25 2.25 0 014.25 4h5a.75.75 0 010 1.5h-5z"
									clip-rule="evenodd"
								/>
								<path
									fill-rule="evenodd"
									d="M6.194 12.753a.75.75 0 001.06.053L16.5 4.44v2.81a.75.75 0 001.5 0v-4.5a.75.75 0 00-.75-.75h-4.5a.75.75 0 000 1.5h2.553l-9.056 8.194a.75.75 0 00-.053 1.06z"
									clip-rule="evenodd"
								/>
							</svg>
							{$i18n.t('View')}
						</button>
					</div>
				</div>
			{/each}
		</div>
	{:else}
		<!-- No Results State -->
		<div class="text-center py-8">
			<svg class="w-12 h-12 text-gray-400 mx-auto mb-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
				<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
			</svg>
			<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
				{$i18n.t('No places found')}
			</h3>
			<p class="text-gray-500 dark:text-gray-400 mb-4">
				{#if data.query}
					{$i18n.t('No places found for "{{query}}"', { query: data.query })}
					{#if data.search_location}
						{$i18n.t(' near {{location}}', { location: data.search_location })}
					{/if}
				{:else}
					{$i18n.t('No places found for this search.')}
				{/if}
			</p>
			<p class="text-sm text-gray-400 dark:text-gray-500">
				{$i18n.t('Try adjusting your search terms or expanding the search area.')}
			</p>
		</div>
	{/if}

	<!-- Summary Statistics (if helpful) -->
	{#if validPlaces.length > 0}
		<div class="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
			<div class="flex flex-wrap items-center gap-4 text-xs text-gray-500 dark:text-gray-400">
				<span>{$i18n.t('{{count}} total results', { count: validPlaces.length })}</span>
				{#if placesWithCoords.length > 0}
					<span>• {$i18n.t('{{count}} with coordinates', { count: placesWithCoords.length })}</span>
				{/if}
				{#if validPlaces.some(p => p.rating)}
					<span>• {$i18n.t('{{count}} with ratings', { count: validPlaces.filter(p => p.rating).length })}</span>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	.line-clamp-2 {
		display: -webkit-box;
		-webkit-line-clamp: 2;
		-webkit-box-orient: vertical;
		overflow: hidden;
	}
</style> 