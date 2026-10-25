/**
 * Geofence utilities — get the user's GPS position and check distance
 * to the assigned work site.
 */

import { Capacitor } from '@capacitor/core';
import { Geolocation } from '@capacitor/geolocation';

export async function getCurrentPosition() {
  if (Capacitor.isNativePlatform()) {
    const permission = await Geolocation.requestPermissions({permissions:['location']});
    if (permission.location !== 'granted') throw new Error('Precise location permission is required for attendance.');
    const position = await Geolocation.getCurrentPosition({enableHighAccuracy:true,timeout:15000,maximumAge:0});
    return {lat:position.coords.latitude,lng:position.coords.longitude,accuracy:position.coords.accuracy};
  }
  return new Promise((resolve, reject) => {
    if (!navigator.geolocation) {
      reject(new Error("Geolocation not supported on this device"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) =>
        resolve({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: pos.coords.accuracy,
        }),
      (err) => reject(err),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
    );
  });
}

function toRad(deg) {
  return (deg * Math.PI) / 180;
}

/** Haversine distance in meters between two lat/lng points. */
export function haversineDistance(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const dLat = toRad(lat2 - lat1);
  const dLng = toRad(lng2 - lng1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLng / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

/**
 * Checks whether the current device is within the site geofence.
 * Returns { within, distance, accuracy }.
 */
export async function checkGeofence(siteLat, siteLng, radius = 200) {
  const pos = await getCurrentPosition();
  const dist = haversineDistance(pos.lat, pos.lng, siteLat, siteLng);
  return {
    within: dist <= radius,
    distance: Math.round(dist),
    accuracy: Math.round(pos.accuracy),
  };
}