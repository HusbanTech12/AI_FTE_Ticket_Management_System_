import SupportForm from '../SupportForm';

export default function Home() {
  const apiEndpoint = process.env.NEXT_PUBLIC_API_URL
    ? `${process.env.NEXT_PUBLIC_API_URL}/support/submit`
    : '/api/support/submit';

  return (
    <>
      <title>FlowSync Support - Contact Us</title>
      <meta name="description" content="Get help with FlowSync platform. Submit support requests via email, WhatsApp, or web form." />
      <SupportForm apiEndpoint={apiEndpoint} />
    </>
  );
}
