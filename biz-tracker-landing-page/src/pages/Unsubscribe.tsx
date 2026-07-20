import { useSearchParams } from "react-router-dom";

const Unsubscribe = () => {
  const [searchParams] = useSearchParams();
  const email = searchParams.get("email");

  return (
    <div className="flex min-h-screen items-center justify-center bg-muted">
      <div className="max-w-md text-center">
        <div className="mb-6 flex justify-center">
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-green-100">
            <svg
              className="h-8 w-8 text-green-600"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
        </div>
        <h1 className="mb-4 text-3xl font-bold">Désabonnement confirmé</h1>
        {email ? (
          <p className="mb-6 text-muted-foreground">
            L'adresse <span className="font-medium text-foreground">{email}</span> a bien été
            désabonnée. Vous ne recevrez plus de notifications de notre part.
          </p>
        ) : (
          <p className="mb-6 text-muted-foreground">
            Votre adresse e-mail a bien été désabonnée. Vous ne recevrez plus de notifications de
            notre part.
          </p>
        )}
        <a href="/" className="text-primary underline hover:text-primary/90">
          Retour à l'accueil
        </a>
      </div>
    </div>
  );
};

export default Unsubscribe;
