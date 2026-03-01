import { LinkedInCheckResponse, LinkedInDebugResponse } from "../types";
import { getAdminToken } from "./auth";
import { ApiError, request } from "./http";

interface LinkedInCheckApiResponse {
  director_id: string;
  first_names: string | null;
  last_name: string | null;
  quality: string | null;
  company_name: string | null;
  linkedin_profile_url: string | null;
  linkedin_profile_data: Record<string, unknown> | null;
  linkedin_check_status: string;
  linkedin_last_checked_at: string | null;
  message: string;
}

interface LinkedInDebugApiResponse {
  director_id: string;
  director_name: string;
  company_name: string;
  search_input: {
    first_name: string;
    last_name: string;
    company: string;
  };
  apify_response: Record<string, unknown> | null;
  profile_url: string | null;
  profile_data: Record<string, unknown> | null;
  status: string;
  error: string | null;
  retried_with_legal_unit: boolean;
}

function mapLinkedInCheckResponse(response: LinkedInCheckApiResponse): LinkedInCheckResponse {
  return {
    directorId: response.director_id,
    firstNames: response.first_names,
    lastName: response.last_name,
    quality: response.quality,
    companyName: response.company_name,
    linkedinProfileUrl: response.linkedin_profile_url,
    linkedinProfileData: response.linkedin_profile_data,
    linkedinCheckStatus: response.linkedin_check_status,
    linkedinLastCheckedAt: response.linkedin_last_checked_at,
    message: response.message,
  };
}

function mapLinkedInDebugResponse(response: LinkedInDebugApiResponse): LinkedInDebugResponse {
  return {
    directorId: response.director_id,
    directorName: response.director_name,
    companyName: response.company_name,
    searchInput: {
      firstName: response.search_input.first_name,
      lastName: response.search_input.last_name,
      company: response.search_input.company,
    },
    apifyResponse: response.apify_response,
    profileUrl: response.profile_url,
    profileData: response.profile_data,
    status: response.status,
    error: response.error,
    retriedWithLegalUnit: response.retried_with_legal_unit,
  };
}

/**
 * Trigger a LinkedIn profile search for a single director.
 * Updates the director's LinkedIn fields in the database.
 */
export async function checkDirectorLinkedIn(
  directorId: string
): Promise<LinkedInCheckResponse> {
  const token = getAdminToken();
  if (!token) {
    throw new ApiError("Authentication required", 401, null);
  }

  const { data } = await request<LinkedInCheckApiResponse>(
    `/admin/directors/${directorId}/linkedin-check`,
    {
      method: "POST",
      headers: {
        "X-Admin-Token": token,
      },
    }
  );

  return mapLinkedInCheckResponse(data);
}

/**
 * Debug LinkedIn search for a director without updating the database.
 * Returns detailed information about the search process.
 */
export async function debugDirectorLinkedIn(
  directorId: string
): Promise<LinkedInDebugResponse> {
  const token = getAdminToken();
  if (!token) {
    throw new ApiError("Authentication required", 401, null);
  }

  const { data } = await request<LinkedInDebugApiResponse>(
    `/admin/directors/${directorId}/linkedin-debug`,
    {
      method: "GET",
      headers: {
        "X-Admin-Token": token,
      },
    }
  );

  return mapLinkedInDebugResponse(data);
}

export const linkedInApi = {
  checkDirectorLinkedIn,
  debugDirectorLinkedIn,
};
