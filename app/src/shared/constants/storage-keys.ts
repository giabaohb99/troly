// Khóa localStorage dùng chung giữa các module (không chứa bí mật).
export const STORAGE_KEYS = {
  // Id thiết bị của máy này, để màn Cài đặt không cho tự thu hồi nhầm.
  currentDeviceId: 'troly.device.id',
} as const
