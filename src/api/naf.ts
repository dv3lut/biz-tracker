import type { Department, NafCategory, NafSubCategory } from "../types";
import { request } from "./http";

export type NafSubCategoryResponse = {
  id: string;
  name: string;
  description: string | null;
  naf_code: string;
  price_cents: number;
  price_eur: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  google_department_count?: number;
  google_department_all?: boolean;
  google_departments?: DepartmentResponse[];
};

type DepartmentResponse = {
  id: string;
  code: string;
  name: string;
  order_index: number;
  region_id: string;
};

type NafCategoryResponse = {
  id: string;
  name: string;
  description: string | null;
  keywords: string[] | null;
  created_at: string;
  updated_at: string;
  subcategories: NafSubCategoryResponse[];
};

export interface NafCategoryPayload {
  name: string;
  description?: string | null;
  keywords: string[];
}

export interface NafSubCategoryCreatePayload {
  categoryId: string;
  name: string;
  nafCode: string;
  description?: string | null;
  priceEur?: number;
  isActive?: boolean;
}

export interface NafSubCategoryUpdatePayload {
  name?: string;
  nafCode?: string;
  description?: string | null;
  priceEur?: number;
  isActive?: boolean;
}

const mapDepartmentResponse = (department: DepartmentResponse): Department => ({
  id: department.id,
  code: department.code,
  name: department.name,
  orderIndex: department.order_index,
  regionId: department.region_id,
});

export const mapNafSubCategoryResponse = (subcategory: NafSubCategoryResponse): NafSubCategory => ({
  id: subcategory.id,
  name: subcategory.name,
  description: subcategory.description,
  nafCode: subcategory.naf_code,
  priceCents: subcategory.price_cents,
  priceEur: subcategory.price_eur,
  isActive: subcategory.is_active,
  createdAt: subcategory.created_at,
  updatedAt: subcategory.updated_at,
  googleDepartmentCount: subcategory.google_department_count ?? 0,
  googleDepartmentAll: subcategory.google_department_all ?? false,
  googleDepartments: (subcategory.google_departments ?? []).map(mapDepartmentResponse),
});

const mapCategoryResponse = (category: NafCategoryResponse): NafCategory => ({
  id: category.id,
  name: category.name,
  description: category.description,
  keywords: category.keywords ?? [],
  createdAt: category.created_at,
  updatedAt: category.updated_at,
  subcategories: (category.subcategories || []).map(mapNafSubCategoryResponse),
});

const serializeCategoryPayload = (payload: NafCategoryPayload) => ({
  name: payload.name,
  description: payload.description ?? null,
  keywords: payload.keywords,
});

const serializeSubCategoryCreatePayload = (payload: NafSubCategoryCreatePayload) => {
  const body: Record<string, unknown> = {
    category_id: payload.categoryId,
    name: payload.name,
    naf_code: payload.nafCode,
    description: payload.description ?? null,
    is_active: payload.isActive ?? true,
  };
  if (payload.priceEur !== undefined) {
    body.price_eur = payload.priceEur;
  }
  return body;
};

const serializeSubCategoryUpdatePayload = (payload: NafSubCategoryUpdatePayload) => {
  const body: Record<string, unknown> = {};
  if (payload.name !== undefined) {
    body.name = payload.name;
  }
  if (payload.nafCode !== undefined) {
    body.naf_code = payload.nafCode;
  }
  if (payload.description !== undefined) {
    body.description = payload.description ?? null;
  }
  if (payload.priceEur !== undefined) {
    body.price_eur = payload.priceEur;
  }
  if (payload.isActive !== undefined) {
    body.is_active = payload.isActive;
  }
  return body;
};

export const nafApi = {
  listCategories: async (): Promise<NafCategory[]> => {
    const response = await request<NafCategoryResponse[]>("/admin/naf-categories");
    return response.data.map(mapCategoryResponse);
  },
  listSubCategories: async (): Promise<NafSubCategory[]> => {
    const response = await request<NafSubCategoryResponse[]>("/admin/naf-subcategories");
    return response.data.map(mapNafSubCategoryResponse);
  },
  createCategory: async (payload: NafCategoryPayload): Promise<NafCategory> => {
    const response = await request<NafCategoryResponse>("/admin/naf-categories", {
      method: "POST",
      body: JSON.stringify(serializeCategoryPayload(payload)),
    });
    return mapCategoryResponse(response.data);
  },
  updateCategory: async (categoryId: string, payload: NafCategoryPayload): Promise<NafCategory> => {
    const response = await request<NafCategoryResponse>(`/admin/naf-categories/${categoryId}`, {
      method: "PUT",
      body: JSON.stringify(serializeCategoryPayload(payload)),
    });
    return mapCategoryResponse(response.data);
  },
  deleteCategory: async (categoryId: string): Promise<void> => {
    await request<void>(`/admin/naf-categories/${categoryId}`, { method: "DELETE" });
  },
  createSubCategory: async (payload: NafSubCategoryCreatePayload): Promise<NafSubCategory> => {
    const response = await request<NafSubCategoryResponse>("/admin/naf-subcategories", {
      method: "POST",
      body: JSON.stringify(serializeSubCategoryCreatePayload(payload)),
    });
    return mapNafSubCategoryResponse(response.data);
  },
  updateSubCategory: async (subcategoryId: string, payload: NafSubCategoryUpdatePayload): Promise<NafSubCategory> => {
    const response = await request<NafSubCategoryResponse>(`/admin/naf-subcategories/${subcategoryId}`, {
      method: "PUT",
      body: JSON.stringify(serializeSubCategoryUpdatePayload(payload)),
    });
    return mapNafSubCategoryResponse(response.data);
  },
  attachSubCategory: async (categoryId: string, subcategoryId: string): Promise<NafSubCategory> => {
    const response = await request<NafSubCategoryResponse>(`/admin/naf-categories/${categoryId}/subcategories`, {
      method: "POST",
      body: JSON.stringify({ subcategory_id: subcategoryId }),
    });
    return mapNafSubCategoryResponse(response.data);
  },
  detachSubCategory: async (categoryId: string, subcategoryId: string): Promise<void> => {
    await request<void>(`/admin/naf-categories/${categoryId}/subcategories/${subcategoryId}`, {
      method: "DELETE",
    });
  },
  deleteSubCategory: async (subcategoryId: string): Promise<void> => {
    await request<void>(`/admin/naf-subcategories/${subcategoryId}`, { method: "DELETE" });
  },
};
