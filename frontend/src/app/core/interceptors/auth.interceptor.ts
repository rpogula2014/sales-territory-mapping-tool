import { HttpInterceptorFn } from '@angular/common/http';

export const authInterceptor: HttpInterceptorFn = (req, next) => {
  // TODO: attach MSAL access token and retry once after silent refresh on 401.
  return next(req);
};
