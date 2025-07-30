<script lang="ts">
	import { getContext } from 'svelte';
	import type { Writable } from 'svelte/store';
	import type { i18n as i18nType } from 'i18next';
	import { formatRating, getFullRatingStars } from '$lib/utils/maps';

	const i18n = getContext<Writable<i18nType>>('i18n');

	export let id: string;
	export let data: {
		place: {
			name: string;
			formatted_address: string;
			phone?: string;
			website?: string;
			opening_hours?: string[];
			rating?: number;
			user_ratings_total?: number;
			reviews?: Array<{
				author: string;
				rating: number;
				text: string;
				time?: string;
			}>;
			photos?: string[];
			place_types?: string[];
			price_level?: number;
		};
		maps_url?: string;
	};

	let selectedPhotoIndex = 0;
	let showAllReviews = false;
	let showAllHours = false;

	const generatePlaceUrl = (): string => {
		if (data.maps_url) {
			return data.maps_url;
		}
		const query = encodeURIComponent(`${data.place.name} ${data.place.formatted_address}`);
		return `https://maps.google.com/maps/search/${query}`;
	};

	const openInGoogleMaps = () => {
		const url = generatePlaceUrl();
		window.open(url, '_blank', 'noopener,noreferrer');
	};

	const getRatingStars = (rating: number): string => {
		return getFullRatingStars(rating);
	};

	const getPriceLevelText = (level: number): string => {
		switch (level) {
			case 1: return '$';
			case 2: return '$$';
			case 3: return '$$$';
			case 4: return '$$$$';
			default: return '';
		}
	};

	const formatPhoneNumber = (phone: string): string => {
		return phone.replace(/(\+\d{1,3})(\d{2,3})(\d{3,4})(\d{4})/, '$1 $2-$3-$4');
	};

	const getCurrentDayHours = (hours: string[]): string | null => {
		const today = new Date().getDay();
		const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
		const todayName = dayNames[today];
		
		const todayHours = hours.find(h => h.toLowerCase().startsWith(todayName.toLowerCase()));
		return todayHours || null;
	};

	const isCurrentlyOpen = (hours: string[]): boolean | null => {
		const todayHours = getCurrentDayHours(hours);
		if (!todayHours) return null;
		
		// Simple heuristic - if it contains "Closed" it's closed
		if (todayHours.toLowerCase().includes('closed')) return false;
		
		// Otherwise assume open (would need more complex time parsing for exact check)
		return true;
	};

	const nextPhoto = () => {
		if (data.place.photos && data.place.photos.length > 0) {
			selectedPhotoIndex = (selectedPhotoIndex + 1) % data.place.photos.length;
		}
	};

	const prevPhoto = () => {
		if (data.place.photos && data.place.photos.length > 0) {
			selectedPhotoIndex = selectedPhotoIndex === 0 
				? data.place.photos.length - 1 
				: selectedPhotoIndex - 1;
		}
	};

	const selectPhoto = (index: number) => {
		selectedPhotoIndex = index;
	};

	const toggleAllReviews = () => {
		showAllReviews = !showAllReviews;
	};

	const toggleAllHours = () => {
		showAllHours = !showAllHours;
	};

	$: displayedReviews = showAllReviews 
		? data.place.reviews || []
		: (data.place.reviews || []).slice(0, 3);

	$: displayedHours = showAllHours 
		? data.place.opening_hours || []
		: (data.place.opening_hours || []).slice(0, 2);
</script>

<div class="w-full my-3">
	<!-- Header -->
	<div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-4">
		<div class="flex items-start justify-between mb-3">
			<div class="flex-1 pr-4">
				<h3 class="text-xl font-semibold text-gray-900 dark:text-gray-100 mb-1">
					{data.place.name}
				</h3>
				
				<!-- Rating and Types -->
				<div class="flex items-center gap-4 mb-2">
					{#if data.place.rating}
						<div class="flex items-center gap-1">
							<span class="text-yellow-400" aria-hidden="true">
								{getRatingStars(data.place.rating)}
							</span>
							<span class="font-medium text-gray-900 dark:text-gray-100">
								{formatRating(data.place.rating)}
							</span>
							{#if data.place.user_ratings_total}
								<span class="text-sm text-gray-600 dark:text-gray-400">
									({data.place.user_ratings_total})
								</span>
							{/if}
						</div>
					{/if}
					
					{#if data.place.price_level}
						<span class="text-green-600 dark:text-green-400 font-medium">
							{getPriceLevelText(data.place.price_level)}
						</span>
					{/if}
				</div>

				<!-- Types -->
				{#if data.place.place_types && data.place.place_types.length > 0}
					<div class="flex flex-wrap gap-1 mb-2">
						{#each data.place.place_types.slice(0, 3) as type}
							<span class="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-gray-100 dark:bg-gray-700 text-gray-800 dark:text-gray-200">
								{type.replace(/_/g, ' ').toLowerCase()}
							</span>
						{/each}
					</div>
				{/if}

				<!-- Address -->
				<p class="text-sm text-gray-600 dark:text-gray-400 mb-3">
					{data.place.formatted_address}
				</p>
			</div>

			<!-- Open in Maps Button -->
			<button
				type="button"
				class="flex-shrink-0 inline-flex items-center gap-2 px-3 py-2 text-sm font-medium text-blue-600 dark:text-blue-400 hover:text-blue-800 dark:hover:text-blue-300 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors duration-150"
				on:click={openInGoogleMaps}
				aria-label="{$i18n.t('Open {{name}} in Google Maps', { name: data.place.name })}"
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

		<!-- Contact Info and Hours Grid -->
		<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
			<!-- Contact Information -->
			<div>
				<h4 class="font-medium text-gray-900 dark:text-gray-100 mb-2">
					{$i18n.t('Contact Information')}
				</h4>
				<div class="space-y-2 text-sm">
					{#if data.place.phone}
						<div class="flex items-center gap-2">
							<svg class="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
								<path fill-rule="evenodd" d="M2 3.5A1.5 1.5 0 013.5 2h1.148a1.5 1.5 0 011.465 1.175l.716 3.223a1.5 1.5 0 01-1.052 1.767l-.933.267c-.41.117-.643.555-.48.95a11.542 11.542 0 006.254 6.254c.395.163.833-.07.95-.48l.267-.933a1.5 1.5 0 011.767-1.052l3.223.716A1.5 1.5 0 0118 15.352V16.5a1.5 1.5 0 01-1.5 1.5H15c-8.284 0-15-6.716-15-15V3.5z" clip-rule="evenodd" />
							</svg>
							<a href="tel:{data.place.phone}" class="text-blue-600 dark:text-blue-400 hover:underline">
								{formatPhoneNumber(data.place.phone)}
							</a>
						</div>
					{/if}
					
					{#if data.place.website}
						<div class="flex items-center gap-2">
							<svg class="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20" aria-hidden="true">
								<path fill-rule="evenodd" d="M4.25 2A2.25 2.25 0 002 4.25v11.5A2.25 2.25 0 004.25 18h11.5A2.25 2.25 0 0018 15.75V4.25A2.25 2.25 0 0015.75 2H4.25zm4.03 6.28a.75.75 0 00-1.06-1.06L4.97 9.47a.75.75 0 000 1.06l2.25 2.25a.75.75 0 001.06-1.06L6.56 10l1.72-1.72zm4.5-1.06a.75.75 0 10-1.06 1.06L13.44 10l-1.72 1.72a.75.75 0 101.06 1.06l2.25-2.25a.75.75 0 000-1.06l-2.25-2.25z" clip-rule="evenodd" />
							</svg>
							<a href={data.place.website} target="_blank" rel="noopener noreferrer" class="text-blue-600 dark:text-blue-400 hover:underline truncate">
								{data.place.website.replace(/^https?:\/\//, '')}
							</a>
						</div>
					{/if}
				</div>
			</div>

			<!-- Opening Hours -->
			{#if data.place.opening_hours && data.place.opening_hours.length > 0}
				<div>
					<h4 class="font-medium text-gray-900 dark:text-gray-100 mb-2 flex items-center gap-2">
						{$i18n.t('Opening Hours')}
						{#if getCurrentDayHours(data.place.opening_hours)}
							{@const isOpen = isCurrentlyOpen(data.place.opening_hours)}
							{#if isOpen !== null}
								<span class="inline-flex items-center gap-1 px-2 py-1 rounded-full text-xs font-medium {isOpen ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-200' : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-200'}">
									<div class="w-1.5 h-1.5 rounded-full {isOpen ? 'bg-green-500' : 'bg-red-500'}"></div>
									{isOpen ? $i18n.t('Open') : $i18n.t('Closed')}
								</span>
							{/if}
						{/if}
					</h4>
					<div class="space-y-1 text-sm">
						{#each displayedHours as hours}
							<div class="text-gray-600 dark:text-gray-400">
								{hours}
							</div>
						{/each}
						{#if data.place.opening_hours.length > 2}
							<button
								type="button"
								class="text-blue-600 dark:text-blue-400 hover:underline text-xs"
								on:click={toggleAllHours}
							>
								{showAllHours ? $i18n.t('Show less') : $i18n.t('Show all hours')}
							</button>
						{/if}
					</div>
				</div>
			{/if}
		</div>
	</div>

	<!-- Photos -->
	{#if data.place.photos && data.place.photos.length > 0}
		<div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4 mb-4">
			<h4 class="font-medium text-gray-900 dark:text-gray-100 mb-3">
				{$i18n.t('Photos')}
			</h4>
			
			<!-- Main Photo -->
			<div class="relative mb-3">
				<img
					src={data.place.photos[selectedPhotoIndex]}
					alt="{$i18n.t('Photo of {{name}}', { name: data.place.name })}"
					class="w-full h-64 object-cover rounded-lg"
				/>
				
				{#if data.place.photos.length > 1}
					<!-- Navigation Arrows -->
					<button
						type="button"
						class="absolute left-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-full p-2 transition-colors"
						on:click={prevPhoto}
						aria-label="{$i18n.t('Previous photo')}"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7" />
						</svg>
					</button>
					
					<button
						type="button"
						class="absolute right-2 top-1/2 -translate-y-1/2 bg-black/50 hover:bg-black/70 text-white rounded-full p-2 transition-colors"
						on:click={nextPhoto}
						aria-label="{$i18n.t('Next photo')}"
					>
						<svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
							<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
						</svg>
					</button>
					
					<!-- Photo Indicators -->
					<div class="absolute bottom-3 left-1/2 -translate-x-1/2 flex gap-1">
						{#each data.place.photos as _, index}
							<button
								type="button"
								class="w-2 h-2 rounded-full transition-colors {index === selectedPhotoIndex ? 'bg-white' : 'bg-white/50'}"
								on:click={() => selectPhoto(index)}
								aria-label="{$i18n.t('View photo {{number}}', { number: index + 1 })}"
							></button>
						{/each}
					</div>
				{/if}
			</div>
			
			<!-- Thumbnail Strip -->
			{#if data.place.photos.length > 1}
				<div class="flex gap-2 overflow-x-auto">
					{#each data.place.photos as photo, index}
						<button
							type="button"
							class="flex-shrink-0 w-16 h-16 rounded-md overflow-hidden border-2 transition-colors {index === selectedPhotoIndex ? 'border-blue-500' : 'border-gray-200 dark:border-gray-600'}"
							on:click={() => selectPhoto(index)}
						>
							<img
								src={photo}
								alt="{$i18n.t('Thumbnail {{number}}', { number: index + 1 })}"
								class="w-full h-full object-cover"
							/>
						</button>
					{/each}
				</div>
			{/if}
		</div>
	{/if}

	<!-- Reviews -->
	{#if data.place.reviews && data.place.reviews.length > 0}
		<div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-4">
			<h4 class="font-medium text-gray-900 dark:text-gray-100 mb-3">
				{$i18n.t('Reviews')}
			</h4>
			
			<div class="space-y-4">
				{#each displayedReviews as review}
					<div class="border-b border-gray-200 dark:border-gray-700 last:border-b-0 pb-4 last:pb-0">
						<div class="flex items-start justify-between mb-2">
							<div>
								<div class="font-medium text-gray-900 dark:text-gray-100 text-sm">
									{review.author}
								</div>
								<div class="flex items-center gap-1">
									<span class="text-yellow-400 text-sm" aria-hidden="true">
										{getRatingStars(review.rating)}
									</span>
									<span class="text-sm text-gray-600 dark:text-gray-400">
										{formatRating(review.rating)}
									</span>
								</div>
							</div>
							{#if review.time}
								<span class="text-xs text-gray-500 dark:text-gray-400">
									{review.time}
								</span>
							{/if}
						</div>
						<p class="text-sm text-gray-600 dark:text-gray-400 leading-relaxed">
							{review.text}
						</p>
					</div>
				{/each}
			</div>
			
			{#if data.place.reviews.length > 3}
				<button
					type="button"
					class="mt-3 text-blue-600 dark:text-blue-400 hover:underline text-sm"
					on:click={toggleAllReviews}
				>
					{showAllReviews 
						? $i18n.t('Show fewer reviews') 
						: $i18n.t('Show all {{count}} reviews', { count: data.place.reviews.length })}
				</button>
			{/if}
		</div>
	{/if}
</div> 