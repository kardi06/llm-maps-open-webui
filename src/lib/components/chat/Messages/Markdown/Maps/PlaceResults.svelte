<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let id: string;
	export let data: {
		places: Array<{
			name: string;
			address: string;
			lat: number;
			lng: number;
			place_id?: string;
			rating?: number;
			open_now?: boolean;
			maps_url?: string;
		}>;
		query?: string;
		total_results?: number;
	};

	const generateMapsUrl = (place: any): string => {
		if (place.maps_url) {
			return place.maps_url;
		}
		if (place.place_id) {
			return `https://maps.google.com/maps/place/?q=place_id:${place.place_id}`;
		}
		return `https://maps.google.com/maps/search/${encodeURIComponent(place.name + ' ' + place.address)}`;
	};

	const openInGoogleMaps = (place: any) => {
		const url = generateMapsUrl(place);
		window.open(url, '_blank', 'noopener,noreferrer');
	};

	const formatRating = (rating: number): string => {
		return rating.toFixed(1);
	};

	const getRatingStars = (rating: number): string => {
		const fullStars = Math.floor(rating);
		const hasHalfStar = rating % 1 >= 0.5;
		let stars = '★'.repeat(fullStars);
		if (hasHalfStar && fullStars < 5) {
			stars += '☆';
		}
		return stars;
	};
</script>

<div class="w-full my-3">
	<!-- Header -->
	{#if data.query}
		<div class="mb-3">
			<h3 class="text-lg font-medium text-gray-900 dark:text-gray-100">
				{$i18n.t('Places for "{{query}}"', { query: data.query })}
			</h3>
			{#if data.total_results}
				<p class="text-sm text-gray-600 dark:text-gray-400">
					{$i18n.t('Showing {{count}} results', { count: data.places.length })}
					{#if data.total_results > data.places.length}
						{$i18n.t('of {{total}}', { total: data.total_results })}
					{/if}
				</p>
			{/if}
		</div>
	{/if}

	<!-- Places Grid -->
	<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
		{#each data.places as place, idx}
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
				<p class="text-sm text-gray-600 dark:text-gray-400 mb-3 line-clamp-2">
					{place.address}
				</p>

				<!-- Status and Actions -->
				<div class="flex justify-between items-center">
					<!-- Open Status -->
					{#if place.open_now !== undefined}
						<div class="flex items-center gap-1">
							<div
								class="w-2 h-2 rounded-full {place.open_now
									? 'bg-green-500'
									: 'bg-red-500'}"
								aria-hidden="true"
							></div>
							<span class="text-xs text-gray-600 dark:text-gray-400">
								{place.open_now ? $i18n.t('Open') : $i18n.t('Closed')}
							</span>
						</div>
					{:else}
						<div></div>
					{/if}

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

	{#if data.places.length === 0}
		<div class="text-center py-8 text-gray-500 dark:text-gray-400">
			<p>{$i18n.t('No places found for this search.')}</p>
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