<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let id: string;
	export let data: {
		route?: {
			steps?: Array<{
				instruction: string;
				distance: string;
				duration: string;
				maneuver?: string;
			}>;
			distance?: string;
			duration?: string;
			start_address?: string;
			end_address?: string;
			overview_polyline?: string;
		};
		travel_mode?: string;
		origin?: string;
		destination?: string;
		summary?: {
			distance?: string;
			duration?: string;
		};
		maps_url?: string;
	};

	let expanded = false;
	let hasValidData = false;

	// Reactive validation of data structure
	$: {
		hasValidData = !!(data && (
			(data.route && (data.route.steps || data.route.distance || data.route.duration)) ||
			(data.summary && (data.summary.distance || data.summary.duration))
		));
	}

	// Extract route information with fallbacks
	$: routeInfo = (() => {
		if (!hasValidData) return null;
		
		// Primary data from route object
		const route = data.route || {};
		const summary = data.summary || {};
		
		return {
			steps: route.steps || [],
			distance: route.distance || summary.distance || 'Unknown',
			duration: route.duration || summary.duration || 'Unknown',
			start_address: route.start_address || data.origin || '',
			end_address: route.end_address || data.destination || '',
			travel_mode: data.travel_mode || 'driving'
		};
	})();

	const generateDirectionsUrl = (): string => {
		if (data.maps_url) {
			return data.maps_url;
		}
		const origin = routeInfo?.start_address || data.origin || '';
		const destination = routeInfo?.end_address || data.destination || '';
		if (!origin || !destination) {
			return 'https://maps.google.com/';
		}
		const mode = routeInfo?.travel_mode?.toLowerCase() || 'driving';
		return `https://maps.google.com/maps/dir/${encodeURIComponent(origin)}/${encodeURIComponent(destination)}?travelmode=${mode}`;
	};

	const openInGoogleMaps = () => {
		const url = generateDirectionsUrl();
		window.open(url, '_blank', 'noopener,noreferrer');
	};

	const getTravelModeIcon = (mode: string): string => {
		switch (mode?.toLowerCase()) {
			case 'walking':
				return '🚶';
			case 'transit':
				return '🚌';
			case 'bicycling':
				return '🚴';
			case 'driving':
			default:
				return '🚗';
		}
	};

	const getStepIcon = (instruction: string): string => {
		if (!instruction) return '📍';
		
		const lower = instruction.toLowerCase();
		if (lower.includes('turn left') || lower.includes('left turn')) return '↰';
		if (lower.includes('turn right') || lower.includes('right turn')) return '↱';
		if (lower.includes('straight') || lower.includes('continue')) return '↑';
		if (lower.includes('merge')) return '🔀';
		if (lower.includes('exit')) return '🛤️';
		if (lower.includes('roundabout')) return '🔄';
		if (lower.includes('arrive') || lower.includes('destination')) return '🏁';
		return '📍';
	};

	const cleanInstruction = (instruction: string): string => {
		if (!instruction) return '';
		
		// Remove HTML tags if present
		return instruction.replace(/<[^>]*>/g, '').trim();
	};

	const toggleExpanded = () => {
		expanded = !expanded;
	};

	const formatDistance = (distance: string): string => {
		if (!distance || distance === 'Unknown') return distance;
		// Ensure consistent formatting
		return distance.trim();
	};

	const formatDuration = (duration: string): string => {
		if (!duration || duration === 'Unknown') return duration;
		// Ensure consistent formatting
		return duration.trim();
	};
</script>

{#if !hasValidData}
	<!-- Error State for Invalid Data -->
	<div class="w-full my-3">
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
						{$i18n.t('Directions Display Error')}
					</h4>
					<p class="text-sm text-red-700 dark:text-red-300 mb-2">
						{$i18n.t('Unable to display directions - invalid or missing route data.')}
					</p>
					{#if data.maps_url || (data.origin && data.destination)}
						<button
							type="button"
							class="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-red-600 dark:text-red-400 hover:text-red-800 dark:hover:text-red-200 hover:bg-red-100 dark:hover:bg-red-800/20 rounded transition-colors duration-150"
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
	</div>
{:else}
	<div class="w-full my-3">
		<!-- Route Summary Header -->
		<div class="bg-blue-50 dark:bg-blue-900/20 rounded-lg p-4 mb-4">
			<div class="flex items-center justify-between mb-3">
				<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100 flex items-center gap-2">
					<span class="text-xl">{getTravelModeIcon(routeInfo.travel_mode)}</span>
					{$i18n.t('Directions')}
				</h3>
				<button
					type="button"
					class="inline-flex items-center gap-1 px-3 py-1.5 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-800/20 rounded transition-colors duration-150"
					on:click={openInGoogleMaps}
					aria-label="{$i18n.t('Open directions in Google Maps')}"
				>
					<svg
						class="w-4 h-4"
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
					{$i18n.t('Open in Maps')}
				</button>
			</div>

			<!-- Route and Destinations -->
			{#if routeInfo.start_address && routeInfo.end_address}
				<div class="mb-3 text-sm text-gray-700 dark:text-gray-300">
					<div class="flex items-start gap-2 mb-1">
						<span class="w-3 h-3 bg-green-500 rounded-full flex-shrink-0 mt-1"></span>
						<div class="flex-1 min-w-0">
							<span class="font-medium">{$i18n.t('From')}: </span>
							<span class="break-words">{routeInfo.start_address}</span>
						</div>
					</div>
					<div class="flex items-start gap-2">
						<span class="w-3 h-3 bg-red-500 rounded-full flex-shrink-0 mt-1"></span>
						<div class="flex-1 min-w-0">
							<span class="font-medium">{$i18n.t('To')}: </span>
							<span class="break-words">{routeInfo.end_address}</span>
						</div>
					</div>
				</div>
			{/if}

			<!-- Summary Stats -->
			<div class="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
				<div class="bg-white dark:bg-gray-800 rounded-md p-3">
					<div class="text-lg font-semibold text-gray-900 dark:text-gray-100">
						{formatDistance(routeInfo.distance)}
					</div>
					<div class="text-sm text-gray-600 dark:text-gray-400">
						{$i18n.t('Distance')}
					</div>
				</div>
				<div class="bg-white dark:bg-gray-800 rounded-md p-3">
					<div class="text-lg font-semibold text-gray-900 dark:text-gray-100">
						{formatDuration(routeInfo.duration)}
					</div>
					<div class="text-sm text-gray-600 dark:text-gray-400">
						{$i18n.t('Duration')}
					</div>
				</div>
				<div class="bg-white dark:bg-gray-800 rounded-md p-3">
					<div class="text-lg font-semibold text-gray-900 dark:text-gray-100 capitalize">
						{routeInfo.travel_mode}
					</div>
					<div class="text-sm text-gray-600 dark:text-gray-400">
						{$i18n.t('Travel Mode')}
					</div>
				</div>
			</div>

			<!-- Show/Hide Steps Toggle -->
			{#if routeInfo.steps && routeInfo.steps.length > 0}
				<button
					type="button"
					class="w-full mt-4 flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-gray-100 hover:bg-white/50 dark:hover:bg-gray-800/50 rounded transition-colors duration-150"
					on:click={toggleExpanded}
					aria-expanded={expanded}
					aria-controls="directions-steps-{id}"
				>
					{expanded ? $i18n.t('Hide Steps') : $i18n.t('Show Steps')} ({routeInfo.steps.length})
					<svg
						class="w-4 h-4 transition-transform duration-200 {expanded ? 'rotate-180' : ''}"
						fill="none"
						stroke="currentColor"
						viewBox="0 0 24 24"
						xmlns="http://www.w3.org/2000/svg"
						aria-hidden="true"
					>
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
					</svg>
				</button>
			{:else if routeInfo.distance !== 'Unknown' || routeInfo.duration !== 'Unknown'}
				<div class="mt-4 text-center text-sm text-gray-600 dark:text-gray-400">
					{$i18n.t('Step-by-step directions not available')}
				</div>
			{/if}
		</div>

		<!-- Detailed Steps -->
		{#if expanded && routeInfo.steps && routeInfo.steps.length > 0}
			<div
				id="directions-steps-{id}"
				class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 divide-y divide-gray-200 dark:divide-gray-700"
				role="list"
				aria-label="{$i18n.t('Turn-by-turn directions')}"
			>
				{#each routeInfo.steps as step, idx}
					<div class="flex items-start gap-3 p-4" role="listitem">
						<!-- Step Number and Icon -->
						<div class="flex-shrink-0 flex flex-col items-center">
							<div
								class="w-8 h-8 bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400 rounded-full flex items-center justify-center text-sm font-medium"
								aria-label="{$i18n.t('Step {{number}}', { number: idx + 1 })}"
							>
								{idx + 1}
							</div>
							{#if idx < routeInfo.steps.length - 1}
								<div class="w-0.5 h-6 bg-gray-200 dark:bg-gray-600 mt-2" aria-hidden="true"></div>
							{/if}
						</div>

						<!-- Step Content -->
						<div class="flex-1 min-w-0">
							<div class="flex items-start gap-2 mb-1">
								<span class="text-lg flex-shrink-0" aria-hidden="true">{getStepIcon(step.instruction)}</span>
								<p class="text-sm text-gray-900 dark:text-gray-100 font-medium leading-relaxed">
									{cleanInstruction(step.instruction)}
								</p>
							</div>
							
							<!-- Distance and Duration -->
							{#if step.distance || step.duration}
								<div class="flex items-center gap-4 text-xs text-gray-600 dark:text-gray-400 mt-2">
									{#if step.distance}
										<span class="flex items-center gap-1">
											<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
												<path d="M3 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1zm0 4a1 1 0 011-1h12a1 1 0 110 2H4a1 1 0 01-1-1z" />
											</svg>
											{step.distance}
										</span>
									{/if}
									{#if step.duration}
										<span class="flex items-center gap-1">
											<svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
												<path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clip-rule="evenodd" />
											</svg>
											{step.duration}
										</span>
									{/if}
								</div>
							{/if}
						</div>
					</div>
				{/each}
			</div>
		{/if}
	</div>
{/if} 