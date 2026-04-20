// iOS 13+ requires DeviceOrientation / DeviceMotion permission granted via user gesture.
// Android grants by default.
// Usage: await requestSensorPermission() inside a click/touch handler.

export async function requestSensorPermission() {
  const results = { orientation: 'unknown', motion: 'unknown' };
  if (typeof DeviceOrientationEvent !== 'undefined' &&
      typeof DeviceOrientationEvent.requestPermission === 'function') {
    try {
      results.orientation = await DeviceOrientationEvent.requestPermission();
    } catch (e) { results.orientation = 'denied'; }
  } else {
    results.orientation = 'granted';
  }
  if (typeof DeviceMotionEvent !== 'undefined' &&
      typeof DeviceMotionEvent.requestPermission === 'function') {
    try {
      results.motion = await DeviceMotionEvent.requestPermission();
    } catch (e) { results.motion = 'denied'; }
  } else {
    results.motion = 'granted';
  }
  return results;
}

export function supportsOrientation() {
  return typeof DeviceOrientationEvent !== 'undefined';
}
export function supportsMotion() {
  return typeof DeviceMotionEvent !== 'undefined';
}
