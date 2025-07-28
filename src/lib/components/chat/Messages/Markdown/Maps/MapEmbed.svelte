<script lang="ts">
	import { onMount, getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { generateEmbedUrl, validateCoordinates } from '$lib/utils/maps';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let id: string;
	export let mode: 'place' | 'search' | 'directions' | 'view' = 'view';
	export let apiKey: string = '';
	
	// Mode-specific props
	export let placeId: string | undefined = undefined;
	export let query: string | undefined = undefined;
	export let origin: string | undefined = undefined;
	export let destination: string | undefined = undefined;
	export let center: string | undefined = undefined;
	export let lat: number | undefined = undefined;
	export let lng: number | undefined = undefined;
	export let zoom: number = 15;
	
	// Display options
	export let maptype: 'roadmap' | 'satellite' = 'roadmap';
	export let height: string = '300px';
	export let width: string = '100%';
	export let language: string | undefined = undefined;
	export let region: string | undefined = undefined;
	
	// Fallback options
	export let showFallback: boolean = true;
	export let fallbackUrl: string | undefined = undefined;

	let embedUrl: string | null = null;
	let embedError: string | null = null;
	let iframeLoaded: boolean = false;
	let iframeError: boolean = false;
	let iframeElement: HTMLIFrameElement;

	// Generate embed URL when props change
	$: {
		try {
			if (!apiKey) {
				embedError = 'API key is required for Google Maps embed';
				embedUrl = null;
			} else {
				const params: any = {
					maptype,
					language,
					region
				};

				// Set mode-specific parameters
				switch (mode) {
					case 'place':
						if (placeId) {
							params.placeId = placeId;
						} else if (query) {
							params.query = query;
						} else {
							throw new Error('Place mode requires either placeId or query');
						}
						break;

					case 'search':
						if (!query) {
							throw new Error('Search mode requires query');
						}
						params.query = query;
						break;

					case 'directions':
						if (!origin || !destination) {
							throw new Error('Directions mode requires both origin and destination');
						}
						params.origin = origin;
						params.destination = destination;
						break;

					case 'view':
						if (center) {
							params.center = center;
						} else if (lat !== undefined && lng !== undefined) {
							if (!validateCoordinates(lat, lng)) {
								throw new Error('Invalid coordinates provided');
							}
							params.center = `${lat},${lng}`;
						}
						params.zoom = zoom;
						break;

					default:
						throw new Error(`Unsupported embed mode: ${mode}`);
				}

				embedUrl = generateEmbedUrl(apiKey, mode, params);
				embedError = null;
			}
		} catch (error) {
			embedError = error instanceof Error ? error.message : 'Unknown error generating embed URL';
			embedUrl = null;
		}
	}

	const handleIframeLoad = () => {
		iframeLoaded = true;
		iframeError = false;
	};

	const handleIframeError = () => {
		iframeError = true;
		iframeLoaded = false;
	};

	const openInGoogleMaps = () => {
		if (fallbackUrl) {
			window.open(fallbackUrl, '_blank', 'noopener,noreferrer');
		} else {
			// Generate a basic Google Maps URL based on the mode
			let url = 'https://maps.google.com/';
			
			switch (mode) {
				case 'place':
					if (placeId) {
						url += `maps/place/?q=place_id:${encodeURIComponent(placeId)}`;
					} else if (query) {
						url += `maps/search/${encodeURIComponent(query)}`;
					}
					break;
				case 'search':
					if (query) {
						url += `maps/search/${encodeURIComponent(query)}`;
					}
					break;
				case 'directions':
					if (origin && destination) {
						url += `maps/dir/${encodeURIComponent(origin)}/${encodeURIComponent(destination)}`;
					}
					break;
				case 'view':
					if (center) {
						url += `maps/@${center},${zoom}z`;
					} else if (lat !== undefined && lng !== undefined) {
						url += `maps/@${lat},${lng},${zoom}z`;
					}
					break;
			}
			
			window.open(url, '_blank', 'noopener,noreferrer');
		}
	};

	onMount(() => {
		// Set up iframe error handling
		if (iframeElement) {
			iframeElement.addEventListener('load', handleIframeLoad);
			iframeElement.addEventListener('error', handleIframeError);
			
			return () => {
				iframeElement.removeEventListener('load', handleIframeLoad);
				iframeElement.removeEventListener('error', handleIframeError);
			};
		}
	});
</script>

<div class="w-full my-3" style="max-width: 100%; overflow: hidden;">
	{#if embedError}
		<!-- Error State -->
		<div class="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4">
			<div class="flex items-start gap-3">
				<svg
					class="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5"
					fill="currentColor"
					viewBox="0 0 20 20"
					xmlns="http://www.w3.org/2000/svg"
					aria-hidden="true"
				>
					<path
						fill-rule="evenodd"
						d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z"
						clip-rule="evenodd"
					/>
				</svg>
				<div class="flex-1">
					<h4 class="text-sm font-medium text-red-800 dark:text-red-200 mb-1">
						{$i18n.t('Map Display Error')}
					</h4>
					<p class="text-sm text-red-700 dark:text-red-300">
						{embedError}
					</p>
					{#if showFallback}
						<button
							type="button"
							class="mt-2 inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 hover:bg-red-100 dark:hover:bg-red-800/20 rounded transition-colors duration-150"
							on:click={openInGoogleMaps}
						>
							<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
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
							{$i18n.t('Open in Google Maps')}
						</button>
					{/if}
				</div>
			</div>
		</div>
	{:else if embedUrl}
		<!-- Map Container -->
		<div class="relative bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden border border-gray-200 dark:border-gray-700">
			<!-- Loading State -->
			{#if !iframeLoaded && !iframeError}
				<div class="absolute inset-0 flex items-center justify-center bg-gray-50 dark:bg-gray-700">
					<div class="flex items-center gap-2 text-gray-600 dark:text-gray-400">
						<svg
							class="w-5 h-5 animate-spin"
							fill="none"
							viewBox="0 0 24 24"
							xmlns="http://www.w3.org/2000/svg"
							aria-hidden="true"
						>
							<circle
								class="opacity-25"
								cx="12"
								cy="12"
								r="10"
								stroke="currentColor"
								stroke-width="4"
							/>
							<path
								class="opacity-75"
								fill="currentColor"
								d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
							/>
						</svg>
						<span class="text-sm">{$i18n.t('Loading map...')}</span>
					</div>
				</div>
			{/if}

			<!-- Iframe Error State -->
			{#if iframeError}
				<div class="absolute inset-0 flex items-center justify-center bg-gray-50 dark:bg-gray-700 p-4">
					<div class="text-center">
						<svg
							class="w-8 h-8 text-gray-400 mx-auto mb-2"
							fill="currentColor"
							viewBox="0 0 20 20"
							xmlns="http://www.w3.org/2000/svg"
							aria-hidden="true"
						>
							<path
								fill-rule="evenodd"
								d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-8-3a1 1 0 00-.867.5 1 1 0 11-1.731-1A3 3 0 0113 8a3.001 3.001 0 01-2 2.83V11a1 1 0 11-2 0v-1a1 1 0 011-1 1 1 0 100-2zm0 8a1 1 0 100-2 1 1 0 000 2z"
								clip-rule="evenodd"
							/>
						</svg>
						<p class="text-sm text-gray-600 dark:text-gray-400 mb-2">
							{$i18n.t('Unable to load map')}
						</p>
						{#if showFallback}
							<button
								type="button"
								class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors duration-150"
								on:click={openInGoogleMaps}
							>
								{$i18n.t('Open in Google Maps')}
							</button>
						{/if}
					</div>
				</div>
			{/if}

			<!-- Map Iframe -->
			<iframe
				bind:this={iframeElement}
				src={embedUrl}
				title={$i18n.t('Google Maps')}
				style="width: {width}; height: {height};"
				class="w-full border-0 block"
				loading="lazy"
				referrerpolicy="no-referrer-when-downgrade"
				sandbox="allow-scripts allow-same-origin allow-popups allow-popups-to-escape-sandbox"
				allow="geolocation"
				aria-label={$i18n.t('Interactive Google Maps showing {{mode}} view', { mode })}
				on:load={handleIframeLoad}
				on:error={handleIframeError}
			></iframe>

			<!-- Overlay Controls -->
			{#if iframeLoaded && showFallback}
				<div class="absolute top-2 right-2">
					<button
						type="button"
						class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-white bg-black/50 hover:bg-black/70 rounded backdrop-blur-sm transition-colors duration-150"
						on:click={openInGoogleMaps}
						title={$i18n.t('Open in Google Maps')}
					>
						<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
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
						<span class="sr-only">{$i18n.t('Open in Google Maps')}</span>
					</button>
				</div>
			{/if}
		</div>
	{:else}
		<!-- No API key or configuration -->
		<div class="bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg p-4">
			<div class="text-center">
				<svg
					class="w-8 h-8 text-gray-400 mx-auto mb-2"
					fill="currentColor"
					viewBox="0 0 20 20"
					xmlns="http://www.w3.org/2000/svg"
					aria-hidden="true"
				>
					<path
						fill-rule="evenodd"
						d="M9.663 17h4.673a1.25 1.25 0 001.25-1.25v-2.5c0-.69.56-1.25 1.25-1.25s1.25.56 1.25 1.25v2.5A2.75 2.75 0 0115.336 18H9.663a2.75 2.75 0 01-2.75-2.75V8.663a2.75 2.75 0 012.75-2.75h2.5c.69 0 1.25.56 1.25 1.25s-.56 1.25-1.25 1.25h-2.5a1.25 1.25 0 00-1.25 1.25v6.587A1.25 1.25 0 009.663 17z"
						clip-rule="evenodd"
					/>
				</svg>
				<p class="text-sm text-gray-600 dark:text-gray-400 mb-2">
					{$i18n.t('Map embed not configured')}
				</p>
				{#if showFallback}
					<button
						type="button"
						class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors duration-150"
						on:click={openInGoogleMaps}
					>
						{$i18n.t('Open in Google Maps')}
					</button>
				{/if}
			</div>
		</div>
	{/if}
</div>

<style>
	/* Ensure iframe is responsive */
	iframe {
		aspect-ratio: 16 / 9;
		min-height: 200px;
	}

	@media (max-width: 640px) {
		iframe {
			aspect-ratio: 4 / 3;
		}
	}
</style> 